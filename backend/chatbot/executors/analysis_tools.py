"""
🔧 AnalysisToolsMixin – Ratio, compare, ranking, gender analysis, grade distribution,
                        teacher distribution, year comparison, province/district summaries.
"""

import logging
from typing import Dict, Any, List, Optional

from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchText, MatchAny, Range

from ..core.constants import (
    REGIONS,
    YEAR_COLLECTIONS,
    YEAR_ALIASES,
    AVAILABLE_YEARS,
    COLLECTION_NAMES,
)

logger = logging.getLogger(__name__)


class AnalysisToolsMixin:
    """Comparison, ranking, ratio, gender, grade, and summary tool implementations."""

    # ------------------------------------------------------------------
    # _get_ratio
    # ------------------------------------------------------------------

    def _get_ratio(self, school_name: str = None, province: str = None, **kwargs) -> Dict[str, Any]:
        """Get student-teacher ratio"""
        conditions = []
        cleaned_school_name = school_name

        if school_name:
            cleaned_school_name, _ = self._normalize_school_name(school_name)
            conditions.append(
                FieldCondition(key="metadata.school_name", match=MatchText(text=cleaned_school_name))
            )
        if province:
            province = self._normalize_province(province)
            conditions.append(
                FieldCondition(key="metadata.province", match=MatchValue(value=province))
            )

        scroll_filter = self._build_filter(conditions)
        results = self._scroll_all(self._get_collection("ratios"), scroll_filter, limit=50)

        ratios = []
        for r in results:
            meta = r.payload.get("metadata", {})
            ratios.append({
                "school_name": meta.get("school_name"),
                "ratio": meta.get("ratio", 0),
                "students": meta.get("total_students", 0),
                "teachers": meta.get("total_teachers", 0),
                "province": meta.get("province"),
            })

        # Fallback: compute ratio from students + teachers
        if not ratios and school_name:
            try:
                student_result = self._count_students(school_name=school_name, province=province)
                teacher_result = self._count_teachers(school_name=school_name, province=province)

                if student_result.get("ambiguous") or teacher_result.get("ambiguous"):
                    logger.info("⚠️ Ratio fallback: ambiguous school name, skipping computed ratio")
                else:
                    total_students = student_result.get("total_students", 0)
                    total_teachers = teacher_result.get("total_teachers", 0)

                    if total_students > 0 and total_teachers > 0:
                        school_label = cleaned_school_name or school_name
                        if student_result.get("by_school"):
                            school_label = next(iter(student_result["by_school"].keys()), school_label)
                        elif teacher_result.get("by_school"):
                            school_label = next(iter(teacher_result["by_school"].keys()), school_label)

                        ratios.append({
                            "school_name": school_label,
                            "ratio": round(total_students / total_teachers, 1),
                            "students": total_students,
                            "teachers": total_teachers,
                            "province": province,
                            "computed": True,
                            "source": "students_teachers"
                        })
                        logger.info("✅ Ratio fallback computed from students + teachers")
            except Exception as e:
                logger.warning(f"⚠️ Ratio fallback failed: {e}")

        return {
            "tool": "get_ratio",
            "query": {"school_name": school_name, "province": province},
            "ratios": sorted(ratios, key=lambda x: x['ratio'], reverse=True)[:10],
            "suggestions": self._suggest_schools(school_name) if not ratios and school_name else None,
            "found": False if not ratios and school_name else True
        }

    # ------------------------------------------------------------------
    # _compare
    # ------------------------------------------------------------------

    def _compare(self, entity1: str, entity2: str, metric: str = "students", **kwargs) -> Dict[str, Any]:
        """Compare two entities (schools, provinces, or regions)"""
        metric_aliases = {
            "จำนวนโรงเรียน": "schools", "โรงเรียน": "schools", "school": "schools",
            "จำนวนนักเรียน": "students", "นักเรียน": "students", "student": "students",
            "จำนวนครู": "teachers", "ครู": "teachers", "teacher": "teachers", "บุคลากร": "teachers",
            "อัตราส่วน": "ratio",
        }
        metric = metric_aliases.get(metric, metric) if metric else "students"
        logger.info(f"📊 [Compare] Normalized metric: {metric}")

        def get_data(entity):
            region = self._normalize_region(entity)
            if region:
                logger.info(f"📍 Detected region entity: {entity} -> {region}")
                return self._get_region_data(region, metric)

            prov_norm = self._normalize_province(entity)

            from ..core.constants import REGIONS as _REGIONS
            all_provinces = set()
            for p_list in _REGIONS.values():
                all_provinces.update(p_list)
            is_province = prov_norm in all_provinces or prov_norm == "กรุงเทพมหานคร"

            if metric == "students":
                if is_province:
                    logger.info(f"📍 Detected province entity: {entity} -> {prov_norm}")
                    return self._count_students(province=prov_norm)

                res_school = self._count_students(school_name=entity)
                if res_school.get("ambiguous") and res_school.get("choices"):
                    choices = res_school["choices"]
                    clean_entity = entity.replace("โรงเรียน", "").strip()
                    for choice in choices:
                        if choice.get("school_name") == entity or choice.get("school_name") == clean_entity:
                            return self._count_students(school_name=choice.get("school_name"), province=choice.get("province"))
                    best = choices[0]
                    return self._count_students(school_name=best.get("school_name"), province=best.get("province"))

                if res_school.get("total_students", 0) > 0:
                    return res_school
                res_prov = self._count_students(province=entity)
                if res_prov.get("total_students", 0) > 0:
                    return res_prov
                return res_school if res_school.get("suggestions") else res_prov

            elif metric == "teachers":
                if is_province:
                    return self._count_teachers(province=prov_norm)

                res_school = self._count_teachers(school_name=entity)
                if res_school.get("ambiguous") and res_school.get("choices"):
                    choices = res_school["choices"]
                    clean_entity = entity.replace("โรงเรียน", "").strip()
                    for choice in choices:
                        if choice.get("school_name") == entity or choice.get("school_name") == clean_entity:
                            return self._count_teachers(school_name=choice.get("school_name"), province=choice.get("province"))
                    best = choices[0]
                    return self._count_teachers(school_name=best.get("school_name"), province=best.get("province"))

                if res_school.get("total_teachers", 0) > 0:
                    return res_school
                res_prov = self._count_teachers(province=entity)
                if res_prov.get("total_teachers", 0) > 0:
                    return res_prov
                return res_school if res_school.get("suggestions") else res_prov

            elif metric == "schools":
                return self._count_schools(province=entity)

            elif metric == "ratio":
                if is_province:
                    return self._get_ratio(province=prov_norm)
                return self._get_ratio(school_name=entity)

            return None

        result1 = get_data(entity1)
        result2 = get_data(entity2)

        return {
            "tool": "compare",
            "entity1": {"name": entity1, "data": result1},
            "entity2": {"name": entity2, "data": result2},
            "metric": metric
        }

    # ------------------------------------------------------------------
    # _ranking
    # ------------------------------------------------------------------

    def _ranking(self, metric: str = None, order: str = "most", scope: str = "school",
                 province: str = None, limit: int = 5, type: str = None, **kwargs) -> Dict[str, Any]:
        """Get ranking of schools or provinces by a metric"""
        if not metric and type:
            metric = type
        if not metric:
            metric = "students"

        region = kwargs.get('region')
        if province and not region:
            if province.startswith("ภาค") or province in REGIONS:
                logger.info(f"🗺️ [Ranking] Province '{province}' is actually a region -> promoting")
                region = province
                kwargs['region'] = region
                province = None

        if region and not province and scope not in ["district", "districts"]:
            logger.info(f"🔄 [Ranking] Downgrading scope from '{scope}' to 'school' (region query without province)")
            scope = "school"

        metric_aliases = {
            "จำนวนครู": "teachers", "ครู": "teachers", "บุคลากร": "teachers", "teacher": "teachers",
            "จำนวนนักเรียน": "students", "นักเรียน": "students", "student": "students",
            "จำนวนโรงเรียน": "schools", "โรงเรียน": "schools", "school": "schools",
            "อัตราส่วน": "ratio", "อัตราส่วนครูต่อนักเรียน": "ratio", "ครูต่อนักเรียน": "ratio",
        }
        metric = metric_aliases.get(metric, metric)
        logger.info(f"📊 [Ranking] Normalized metric: {metric}")

        limit = int(limit)

        scope_norm = scope or "school"
        if scope_norm in ["region", "regions"]:
            if metric not in ["schools", "students", "teachers", "ratio"]:
                return {"error": f"Ranking metric '{metric}' not supported"}

            explicit_region = kwargs.get("region")
            target_regions: List[str] = []
            if explicit_region:
                normalized_region = self._normalize_region(explicit_region) or explicit_region
                if normalized_region in REGIONS:
                    target_regions = [normalized_region]
                else:
                    return {"error": f"ไม่รู้จักภาค '{explicit_region}'"}
            else:
                canonical_regions = [
                    "ภาคเหนือ", "ภาคตะวันออกเฉียงเหนือ", "ภาคกลาง",
                    "ภาคตะวันออก", "ภาคตะวันตก", "ภาคใต้",
                ]
                target_regions = [r for r in canonical_regions if REGIONS.get(r)]

            items = []
            for region_name in target_regions:
                region_data = self._get_region_data(region_name, metric)
                if region_data.get("error"):
                    continue
                items.append((region_name, region_data.get("total", 0)))

        elif metric in ["students", "teachers", "ratio"] and scope_norm in ["province", "provinces", "district", "districts", "subdistrict", "subdistricts"]:
            group_key_map = {
                "province": "province", "provinces": "province",
                "district": "district", "districts": "district",
                "subdistrict": "subdistrict", "subdistricts": "subdistrict",
            }
            group_key = group_key_map.get(scope_norm, "province")
            if group_key in ["district", "subdistrict"] and not province and not kwargs.get("region"):
                return {"error": f"Ranking by {group_key} requires province or region"}

            conditions = []
            if kwargs.get("region"):
                provinces = REGIONS.get(kwargs.get("region"), [])
                if provinces:
                    conditions.append(
                        FieldCondition(key="metadata.province", match=MatchAny(any=provinces))
                    )
            if province:
                conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))
            if group_key == "subdistrict" and kwargs.get("district"):
                conditions.append(FieldCondition(key="metadata.district", match=MatchText(text=kwargs.get("district"))))

            person_type = kwargs.get("person_type")
            is_teacher_type_ranking = metric == "teachers" and person_type

            if is_teacher_type_ranking:
                logger.info(f"📊 [Ranking] Specialized ranking for teachers by person_type: {person_type}")
                person_type = self._normalize_person_type(person_type)
                conditions.append(FieldCondition(key="metadata.person_type", match=MatchValue(value=person_type)))
                scroll_filter = self._build_filter(conditions)
                results = self._scroll_all(
                    self._get_collection("teachers"), scroll_filter, limit=200000,
                    with_payload=["metadata.province", "metadata.district", "metadata.subdistrict", "metadata.count"],
                )
            else:
                scroll_filter = self._build_filter(conditions)
                results = self._scroll_all(
                    self._get_collection("schools"), scroll_filter, limit=200000,
                    with_payload=["metadata.province", "metadata.district", "metadata.subdistrict", "metadata.total_students", "metadata.total_teachers"],
                )

            aggregates: Dict[str, Dict[str, float]] = {}
            for r in results:
                meta = r.payload.get("metadata", {})

                if group_key == "district" and not province and kwargs.get("region"):
                    k_dist = meta.get("district")
                    k_prov = meta.get("province")
                    if not k_dist or not k_prov:
                        continue
                    key = f"{k_prov} - {k_dist}"
                else:
                    key = meta.get(group_key)
                    if not key:
                        continue

                entry = aggregates.setdefault(key, {"students": 0, "teachers": 0})

                if is_teacher_type_ranking:
                    teachers = meta.get("count", 1)
                    if isinstance(teachers, (int, float)):
                        entry["teachers"] += teachers
                else:
                    students = meta.get("total_students") or 0
                    teachers = meta.get("total_teachers") or 0
                    if isinstance(students, (int, float)):
                        entry["students"] += students
                    if isinstance(teachers, (int, float)):
                        entry["teachers"] += teachers

            items = []
            for name, totals in aggregates.items():
                if metric == "students":
                    count = totals["students"]
                elif metric == "teachers":
                    count = totals["teachers"]
                else:
                    if not totals["students"]:
                        continue
                    count = totals["teachers"] / totals["students"]
                items.append((name, count))

        elif metric == "students":
            if kwargs.get('region'):
                data = self._count_students(region=kwargs.get('region'))
                items = [(k, v["total"]) for k, v in data.get("by_school", {}).items()]
            else:
                data = self._count_students(province=province)
                items = [(k, v["total"]) for k, v in data.get("by_school", {}).items()]
        elif metric == "teachers":
            if kwargs.get('region'):
                data = self._count_teachers(region=kwargs.get('region'))
                items = [(k, v["total"]) for k, v in data.get("by_school", {}).items()]
            else:
                data = self._count_teachers(province=province)
                items = [(k, v["total"]) for k, v in data.get("by_school", {}).items()]
        elif metric == "schools":
            if scope in ["district", "districts"]:
                if not province and not kwargs.get("region"):
                    return {"error": "Ranking by district requires province or region"}

                conditions = []
                if kwargs.get("region"):
                    provinces = REGIONS.get(kwargs.get("region"), [])
                    if provinces:
                        conditions.append(FieldCondition(key="metadata.province", match=MatchAny(any=provinces)))
                if province:
                    conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))
                if kwargs.get("district"):
                    conditions.append(FieldCondition(key="metadata.district", match=MatchText(text=kwargs.get("district"))))

                scroll_filter = self._build_filter(conditions)
                results = self._scroll_all(
                    self._get_collection("schools"), scroll_filter, limit=200000,
                    with_payload=["metadata.province", "metadata.district"]
                )
                counts = {}
                for r in results:
                    meta = r.payload.get("metadata", {})
                    dist = meta.get("district")
                    if not dist:
                        continue
                    if not province and kwargs.get("region"):
                        prov = meta.get("province")
                        if prov:
                            dist = f"{prov} - {dist}"
                    counts[dist] = counts.get(dist, 0) + 1
                items = list(counts.items())
            elif scope in ["subdistrict", "subdistricts"]:
                if not province:
                    return {"error": "Ranking by subdistrict requires province"}
                conditions = [FieldCondition(key="metadata.province", match=MatchValue(value=province))]
                if kwargs.get("district"):
                    conditions.append(FieldCondition(key="metadata.district", match=MatchText(text=kwargs.get("district"))))
                scroll_filter = self._build_filter(conditions)
                results = self._scroll_all(
                    self._get_collection("schools"), scroll_filter, limit=200000,
                    with_payload=["metadata.subdistrict"]
                )
                counts = {}
                for r in results:
                    meta = r.payload.get("metadata", {})
                    sub = meta.get("subdistrict")
                    if not sub:
                        continue
                    counts[sub] = counts.get(sub, 0) + 1
                items = list(counts.items())
            elif scope in ["province", "provinces"] or (not province and scope == "school"):
                scope = "province"
                conditions = []
                if kwargs.get('region'):
                    provinces = REGIONS.get(kwargs.get('region'), [])
                    if provinces:
                        conditions.append(
                            FieldCondition(key="metadata.province", match=MatchAny(any=provinces))
                        )
                scroll_filter = self._build_filter(conditions)
                results = self._scroll_all(
                    self._get_collection("schools"), scroll_filter, limit=200000,
                    with_payload=["metadata.province"]
                )
                counts = {}
                for r in results:
                    meta = r.payload.get("metadata", {})
                    prov = meta.get("province")
                    if not prov:
                        continue
                    counts[prov] = counts.get(prov, 0) + 1
                items = list(counts.items())
            else:
                return {"error": "Ranking metric 'schools' requires province scope"}
        else:
            return {"error": f"Ranking metric '{metric}' not supported"}

        reverse = order == "most"
        items.sort(key=lambda x: x[1], reverse=reverse)

        ranking = []
        for i, (name, count) in enumerate(items[:limit], 1):
            ranking.append({"rank": i, "name": name, "count": count})

        result = {
            "tool": "ranking",
            "metric": metric,
            "order": order,
            "scope": scope,
            "province": province,
            "ranking": ranking,
            "guidance": "REQUIRED: Start with an intro (e.g. 'Here are the top schools...') and END with an analysis of the #1 school."
        }
        logger.info(f"DEBUG RANKING RESULT: {result}")
        return result

    # ------------------------------------------------------------------
    # Gender / Grade / System-type analysis
    # ------------------------------------------------------------------

    def _count_by_system_type(self, province: str = None, district: str = None,
                              system_type: str = None) -> Dict[str, Any]:
        """Count schools by system type (Formal/Informal)"""
        conditions = []
        if province:
            province = self._normalize_province(province)
            conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))
        if district:
            conditions.append(FieldCondition(key="metadata.district", match=MatchText(text=district)))
        if system_type:
            conditions.append(FieldCondition(key="metadata.system_type", match=MatchValue(value=system_type)))

        scroll_filter = self._build_filter(conditions)
        results = self._scroll_all(self._get_collection("systems"), scroll_filter)

        by_system = {}
        total_schools = 0

        for r in results:
            meta = r.payload.get("metadata", {})
            sys_type = meta.get("system_type", "ไม่ระบุ")
            count = meta.get("count", meta.get("total_schools", 0))
            by_system[sys_type] = by_system.get(sys_type, 0) + count
            total_schools += count

        return {
            "tool": "count_by_system_type",
            "query": {"province": province, "district": district, "system_type": system_type},
            "total_schools": total_schools,
            "by_system": by_system
        }

    def _analyze_gender_ratio(self, province: str = None, district: str = None,
                              school_name: str = None, **kwargs) -> Dict[str, Any]:
        """Analyze gender distribution of students (Area or Specific School)"""
        if school_name:
            logger.info(f"🔄 [AnalyzeGender] Delegating specific school query '{school_name}' to get_school_full_details")
            details = self._get_school_full_details(school_name, province)

            if details.get("found"):
                student_breakdown = details.get("student_breakdown", {})
                teacher_breakdown = details.get("teacher_breakdown", {})

                total_male_students = sum(d.get("male", 0) for d in student_breakdown.values())
                total_female_students = sum(d.get("female", 0) for d in student_breakdown.values())
                total_male_teachers = teacher_breakdown.get("by_gender", {}).get("male", 0)
                total_female_teachers = teacher_breakdown.get("by_gender", {}).get("female", 0)

                return {
                    "tool": "analyze_gender_ratio",
                    "mode": "school_specific",
                    "school_name": details.get("school_name"),
                    "total_students": details.get("total_students", 0),
                    "student_gender": {
                        "male": total_male_students,
                        "female": total_female_students,
                        "ratio": f"{total_male_students}:{total_female_students}" if total_female_students else "N/A"
                    },
                    "teacher_gender": {
                        "male": total_male_teachers,
                        "female": total_female_teachers
                    },
                    "ai_summary": (
                        f"โรงเรียน {details.get('school_name')} มีนักเรียนทั้งหมด {details.get('total_students', 0):,} คน "
                        f"(ชาย {total_male_students:,}, หญิง {total_female_students:,}) "
                        f"และมีครูทั้งหมด {details.get('total_teachers', 0):,} คน "
                        f"(ชาย {total_male_teachers:,}, หญิง {total_female_teachers:,}) "
                        f"ครับ"
                    )
                }
            else:
                return {"tool": "analyze_gender_ratio", "error": f"School '{school_name}' not found"}

        conditions = []
        if province:
            province = self._normalize_province(province)
            conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))
        if district:
            conditions.append(FieldCondition(key="metadata.district", match=MatchText(text=district)))

        scroll_filter = self._build_filter(conditions)
        results = self._scroll_all(self._get_collection("gender"), scroll_filter)

        total_students = 0
        total_male = 0
        total_female = 0

        for r in results:
            meta = r.payload.get("metadata", {})
            gender = meta.get("gender", "").strip()
            count = meta.get("count", 0)

            if gender in ["ชาย", "male", "Male"]:
                total_male += count
                total_students += count
            elif gender in ["หญิง", "female", "Female"]:
                total_female += count
                total_students += count
            else:
                male = meta.get("male_students", 0)
                female = meta.get("female_students", 0)
                total_male += male
                total_female += female
                total_students += male + female

        return {
            "tool": "analyze_gender_ratio",
            "query": {"province": province, "district": district},
            "overview": {
                "total_students": total_students,
                "male": total_male,
                "female": total_female,
                "male_ratio": round((total_male / total_students) * 100, 1) if total_students > 0 else 0,
                "female_ratio": round((total_female / total_students) * 100, 1) if total_students > 0 else 0,
            }
        }

    def _get_grade_distribution(self, province: str = None, district: str = None,
                                grade: str = None, school_name: str = None) -> Dict[str, Any]:
        """Get student distribution by grade level (School-Specific OR Area-Aggregate)"""
        related_summary = None

        if school_name:
            ambiguity_check = self._resolve_school_ambiguity(school_name, province)

            target_school_id = None
            if ambiguity_check['type'] == 'single':
                target_school_id = ambiguity_check['data'].payload.get('metadata', {}).get('school_id')
            elif ambiguity_check['type'] == 'ambiguous':
                exact = [c for c in ambiguity_check['choices'] if c.get('school_name') == school_name]
                if len(exact) == 1:
                    target_school_id = exact[0].get('school_id')

            if target_school_id:
                stats = self.search_engine.get_student_statistics(target_school_id)
                if stats and "by_grade" in stats:
                    by_grade = stats["by_grade"]
                    grade_order = [
                        'อนุบาล 1', 'อนุบาล 2', 'อนุบาล 3',
                        'ประถมศึกษาปีที่ 1', 'ประถมศึกษาปีที่ 2', 'ประถมศึกษาปีที่ 3',
                        'ประถมศึกษาปีที่ 4', 'ประถมศึกษาปีที่ 5', 'ประถมศึกษาปีที่ 6',
                        'มัธยมศึกษาปีที่ 1', 'มัธยมศึกษาปีที่ 2', 'มัธยมศึกษาปีที่ 3',
                        'มัธยมศึกษาปีที่ 4', 'มัธยมศึกษาปีที่ 5', 'มัธยมศึกษาปีที่ 6',
                        'ปวช.1', 'ปวช.2', 'ปวช.3'
                    ]

                    raw_list = [{"grade": g, "count": data["total"], "male": data["male"], "female": data["female"]}
                                for g, data in by_grade.items()]

                    sorted_grades = []
                    for g_name in grade_order:
                        found = next((x for x in raw_list if x["grade"] == g_name), None)
                        if found:
                            sorted_grades.append(found)
                            raw_list.remove(found)
                    sorted_grades.extend(raw_list)

                    total = sum(x["count"] for x in sorted_grades)

                    return {
                        "tool": "get_grade_distribution",
                        "query": {"school_name": school_name, "school_id": target_school_id},
                        "total_students": total,
                        "distribution": sorted_grades,
                        "mode": "school_specific"
                    }

                try:
                    details = self.search_engine.get_school_details(school_name)
                    if details:
                        related_summary = {
                            "school_name": details.get("school_name"),
                            "province": details.get("province"),
                            "district": details.get("district"),
                            "total_students": details.get("total_students", 0),
                            "total_teachers": details.get("total_teachers", 0),
                            "ratio": details.get("ratio", 0)
                        }
                except Exception as e:
                    logger.warning(f"⚠️ [GetGradeDist] Related summary failed: {e}")
            else:
                logger.warning(f"⚠️ [GetGradeDist] School '{school_name}' not resolved. Falling back to area aggregation.")

        conditions = []
        if province:
            province = self._normalize_province(province)
            conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))
        if district:
            conditions.append(FieldCondition(key="metadata.district", match=MatchText(text=district)))
        if grade:
            grade = self._normalize_grade(grade)

        scroll_filter = self._build_filter(conditions)
        results = self._scroll_all(self._get_collection("grades"), scroll_filter)

        grade_counts = {}
        total_students = 0

        for r in results:
            meta = r.payload.get("metadata", {})
            g = meta.get("grade", "ไม่ระบุ")
            count = meta.get("count", 0) or 0

            if grade and g != grade:
                continue

            grade_counts[g] = grade_counts.get(g, 0) + count
            total_students += count

        grade_order = [
            'อนุบาล 1', 'อนุบาล 2', 'อนุบาล 3',
            'ประถมศึกษาปีที่ 1', 'ประถมศึกษาปีที่ 2', 'ประถมศึกษาปีที่ 3',
            'ประถมศึกษาปีที่ 4', 'ประถมศึกษาปีที่ 5', 'ประถมศึกษาปีที่ 6',
            'มัธยมศึกษาปีที่ 1', 'มัธยมศึกษาปีที่ 2', 'มัธยมศึกษาปีที่ 3',
            'มัธยมศึกษาปีที่ 4', 'มัธยมศึกษาปีที่ 5', 'มัธยมศึกษาปีที่ 6',
            'ปวช.1', 'ปวช.2', 'ปวช.3'
        ]

        sorted_grades = []
        for g in grade_order:
            if g in grade_counts:
                sorted_grades.append({"grade": g, "count": grade_counts[g]})
                del grade_counts[g]

        for g, c in grade_counts.items():
            sorted_grades.append({"grade": g, "count": c})

        result = {
            "tool": "get_grade_distribution",
            "query": {"province": province, "district": district, "grade": grade},
            "total_students": total_students,
            "distribution": sorted_grades
        }

        if not sorted_grades:
            try:
                fallback = self._count_students(province=province, district=district)
                related_summary = {
                    "province": province,
                    "district": district,
                    "total_students": fallback.get("total_students", 0),
                    "by_gender": fallback.get("by_gender", {})
                }
            except Exception as e:
                logger.warning(f"⚠️ [GetGradeDist] Fallback totals failed: {e}")

        if related_summary:
            result["related_summary"] = related_summary

        return result

    def _find_best_ratio_schools(self, province: str = None, order: str = "best",
                                 limit: int = 10) -> Dict[str, Any]:
        """Find schools with best/worst student-teacher ratio"""
        conditions = []

        if province:
            province = self._normalize_province(province)
            conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))

        conditions.append(FieldCondition(key="metadata.ratio", range=None))

        scroll_filter = self._build_filter(conditions)
        results = self._scroll_all(self._get_collection("ratios"), scroll_filter, limit=5000)

        schools = []
        for r in results:
            meta = r.payload.get("metadata", {})
            ratio = meta.get("ratio", 0)

            if ratio <= 0 or ratio > 100:
                continue

            schools.append({
                "school_name": meta.get("school_name"),
                "province": meta.get("province"),
                "ratio": ratio,
                "students": meta.get("total_students", 0),
                "teachers": meta.get("total_teachers", 0)
            })

        reverse = (order == "worst")
        schools.sort(key=lambda x: x["ratio"], reverse=reverse)

        return {
            "tool": "find_best_ratio_schools",
            "query": {"province": province, "order": order},
            "schools": schools[:int(limit)]
        }

    # ------------------------------------------------------------------
    # Phase 3 tools
    # ------------------------------------------------------------------

    def _analyze_teacher_distribution(self, province: str = None, district: str = None,
                                      region: str = None, person_type: str = None,
                                      gender: str = None) -> Dict[str, Any]:
        """Analyze teacher distribution by person type, optionally filtered by gender"""
        conditions = []

        if person_type:
            person_type = self._normalize_person_type(person_type)

        if gender:
            gender_map = {
                'ชาย': 'ชาย', 'male': 'ชาย', 'ผู้ชาย': 'ชาย', 'm': 'ชาย',
                'หญิง': 'หญิง', 'female': 'หญิง', 'ผู้หญิง': 'หญิง', 'f': 'หญิง',
            }
            gender = gender_map.get(gender.strip().lower(), gender.strip())
            if gender in ('ชาย', 'หญิง'):
                conditions.append(FieldCondition(key="metadata.gender", match=MatchValue(value=gender)))

        if province:
            province = self._normalize_province(province)
            conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))
        if district:
            conditions.append(FieldCondition(key="metadata.district", match=MatchText(text=district)))

        if region:
            region = self._normalize_region(region)
            if region:
                region_provinces = REGIONS.get(region, [])
                if region_provinces:
                    province_conditions = [
                        FieldCondition(key="metadata.province", match=MatchValue(value=prov))
                        for prov in region_provinces
                    ]
                    conditions.append(Filter(should=province_conditions))

        scroll_filter = self._build_filter(conditions)
        results = self._scroll_all(self._get_collection("teachers"), scroll_filter)

        type_counts = {}
        total = 0
        male_total = 0
        female_total = 0

        for r in results:
            meta = r.payload.get("metadata", {})
            ptype = meta.get("person_type", "ไม่ระบุ")
            count = meta.get("count", 0)
            gender = meta.get("gender", "")

            if person_type and ptype != person_type:
                continue

            if ptype not in type_counts:
                type_counts[ptype] = {"total": 0, "male": 0, "female": 0}
            type_counts[ptype]["total"] += count

            if gender == "ชาย":
                type_counts[ptype]["male"] += count
                male_total += count
            elif gender == "หญิง":
                type_counts[ptype]["female"] += count
                female_total += count
            total += count

        sorted_types = sorted(type_counts.items(), key=lambda x: x[1]["total"], reverse=True)

        return {
            "tool": "analyze_teacher_distribution",
            "query": {"province": province, "district": district, "region": region, "person_type": person_type, "gender": gender},
            "total_teachers": total,
            "by_gender": {"male": male_total, "female": female_total},
            "by_type": [{"type": t, "total": v["total"], "male": v["male"], "female": v["female"]}
                       for t, v in sorted_types]
        }

    def _ranking_by_agency(self, province: str = None, metric: str = "schools",
                           limit: int = 10) -> Dict[str, Any]:
        """Rank agencies by schools/students/teachers count"""
        conditions = []
        if province:
            province = self._normalize_province(province)
            conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))

        scroll_filter = self._build_filter(conditions)
        results = self._scroll_all(self._get_collection("schools"), scroll_filter)

        agency_counts = {}
        for r in results:
            meta = r.payload.get("metadata", {})
            agency = meta.get("agency", "ไม่ระบุสังกัด")
            if agency not in agency_counts:
                agency_counts[agency] = 0
            agency_counts[agency] += 1

        sorted_agencies = sorted(agency_counts.items(), key=lambda x: x[1], reverse=True)[:int(limit)]

        return {
            "tool": "ranking_by_agency",
            "query": {"province": province, "metric": metric, "limit": limit},
            "ranking": [{"rank": i + 1, "agency": a, "count": c} for i, (a, c) in enumerate(sorted_agencies)]
        }

    def _ranking_subdistricts(self, province: str, district: str = None,
                              metric: str = "schools", order: str = "most",
                              limit: int = 10) -> Dict[str, Any]:
        """Rank subdistricts by schools/students/teachers count"""
        conditions = []
        province = self._normalize_province(province)
        conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))
        if district:
            conditions.append(FieldCondition(key="metadata.district", match=MatchText(text=district)))

        scroll_filter = self._build_filter(conditions)
        results = self._scroll_all(self._get_collection("schools"), scroll_filter)

        subdistrict_counts = {}
        for r in results:
            meta = r.payload.get("metadata", {})
            sub = meta.get("subdistrict", meta.get("sub_district", "ไม่ระบุ"))
            if sub not in subdistrict_counts:
                subdistrict_counts[sub] = 0
            subdistrict_counts[sub] += 1

        reverse = (order == "most")
        sorted_subs = sorted(subdistrict_counts.items(), key=lambda x: x[1], reverse=reverse)[:int(limit)]

        return {
            "tool": "ranking_subdistricts",
            "query": {"province": province, "district": district, "metric": metric, "order": order},
            "ranking": [{"rank": i + 1, "subdistrict": s, "count": c} for i, (s, c) in enumerate(sorted_subs)]
        }

    # ------------------------------------------------------------------
    # Province / District summaries
    # ------------------------------------------------------------------

    def _get_province_summary(self, province: str, **kwargs) -> Dict[str, Any]:
        """Get comprehensive summary of education data for a province"""
        province = self._normalize_province(province)

        school_data = self._count_schools(province=province)
        student_data = self._count_students(province=province)
        teacher_data = self._count_teachers(province=province)
        area_data = self._search_education_areas(province=province)

        ratio_conditions = [
            FieldCondition(key="metadata.province", match=MatchValue(value=province))
        ]
        ratio_filter = self._build_filter(ratio_conditions)
        ratio_results = self._scroll_all(self._get_collection("ratios"), ratio_filter, limit=100)

        ratios = [r.payload.get("metadata", {}).get("ratio", 0) for r in ratio_results if r.payload.get("metadata", {}).get("ratio")]
        avg_ratio = sum(ratios) / len(ratios) if ratios else 0

        summary = {
            "province": province,
            "schools": {
                "total": school_data.get("total_schools", 0),
                "by_agency": school_data.get("by_agency", {}),
            },
            "students": {
                "total": student_data.get("total_students", 0),
                "by_gender": student_data.get("by_gender", {}),
            },
            "teachers": {
                "total": teacher_data.get("total_teachers", 0),
                "by_gender": teacher_data.get("by_gender", {}),
                "by_person_type": teacher_data.get("by_person_type", {}),
            },
            "education_areas": {
                "total": area_data.get("total_found", 0),
                "areas": [a["area_name"] for a in area_data.get("areas", [])],
            },
            "ratio": {
                "average": round(avg_ratio, 1),
                "schools_with_data": len(ratios),
            }
        }

        return {
            "tool": "get_province_summary",
            "query": {"province": province},
            "summary": summary
        }

    def _get_national_summary(self, **kwargs) -> Dict[str, Any]:
        """Get comprehensive national-level education summary (all 3 key metrics + ratio + per-region breakdown)"""
        # ── Core totals ─────────────────────────────────
        school_data = self._count_schools()
        student_data = self._count_students()
        teacher_data = self._count_teachers()

        total_schools = school_data.get("total_schools", 0)
        total_students = student_data.get("total_students", 0)
        total_teachers = teacher_data.get("total_teachers", 0)
        ratio = round(total_students / total_teachers, 2) if total_teachers else 0

        # ── Per-region breakdown ─────────────────────────
        canonical_regions = [
            "ภาคเหนือ", "ภาคตะวันออกเฉียงเหนือ", "ภาคกลาง",
            "ภาคตะวันออก", "ภาคตะวันตก", "ภาคใต้",
        ]
        by_region = []
        for region_name in canonical_regions:
            if not REGIONS.get(region_name):
                continue
            s = self._get_region_data(region_name, "students")
            t = self._get_region_data(region_name, "teachers")
            sch = self._get_region_data(region_name, "schools")
            r_students = s.get("total", 0)
            r_teachers = t.get("total", 0)
            r_schools = sch.get("total", 0)
            r_ratio = round(r_students / r_teachers, 2) if r_teachers else 0
            by_region.append({
                "region": region_name,
                "schools": r_schools,
                "students": r_students,
                "teachers": r_teachers,
                "ratio": r_ratio,
            })

        return {
            "tool": "get_national_summary",
            "summary": {
                "total_schools": total_schools,
                "total_students": total_students,
                "total_teachers": total_teachers,
                "ratio": ratio,
                "by_gender_students": student_data.get("by_gender", {}),
                "by_gender_teachers": teacher_data.get("by_gender", {}),
                "by_agency": school_data.get("by_agency", {}),
                "by_region": by_region,
            },
            "guidance": (
                "REQUIRED: Present a clear national overview table with the 3 metrics "
                "(schools, students, teachers) and the ratio. Also include a per-region "
                "breakdown table. Use Thai language."
            ),
        }

    def _get_district_summary(self, province: str, district: str, **kwargs) -> Dict[str, Any]:
        """Get comprehensive summary for a district"""
        province = self._normalize_province(province)

        school_conditions = [
            FieldCondition(key="metadata.province", match=MatchValue(value=province)),
            FieldCondition(key="metadata.district", match=MatchText(text=district))
        ]
        school_filter = self._build_filter(school_conditions)
        schools = self._scroll_all(self._get_collection("schools"), school_filter)

        subdistricts = set()
        agencies = {}

        for r in schools:
            meta = r.payload.get("metadata", {})
            sub = meta.get("subdistrict", meta.get("sub_district", ""))
            if sub:
                subdistricts.add(sub)
            agency = meta.get("agency", "ไม่ระบุ")
            agencies[agency] = agencies.get(agency, 0) + 1

        student_filter = self._build_filter(school_conditions)
        students = self._scroll_all(self._get_collection("students"), student_filter)
        total_students = sum(r.payload.get("metadata", {}).get("count", 0) for r in students)

        teacher_filter = self._build_filter(school_conditions)
        teachers = self._scroll_all(self._get_collection("teachers"), teacher_filter)
        total_teachers = sum(r.payload.get("metadata", {}).get("count", 0) for r in teachers)

        return {
            "tool": "get_district_summary",
            "query": {"province": province, "district": district},
            "summary": {
                "total_schools": len(schools),
                "total_students": total_students,
                "total_teachers": total_teachers,
                "num_subdistricts": len(subdistricts),
                "subdistricts": list(subdistricts)[:10],
                "by_agency": [{"agency": a, "count": c} for a, c in sorted(agencies.items(), key=lambda x: x[1], reverse=True)]
            }
        }

    def _compare_provinces(self, provinces, metrics: str = "all", **kwargs) -> Dict[str, Any]:
        """Compare education data between multiple provinces"""
        if isinstance(provinces, list):
            province_list = [p.strip() for p in provinces if p]
        else:
            province_list = [p.strip() for p in str(provinces).split(",")]
        results = []

        for prov in province_list:
            prov = self._normalize_province(prov)

            school_filter = self._build_filter([
                FieldCondition(key="metadata.province", match=MatchValue(value=prov))
            ])
            schools = self._scroll_all(self._get_collection("schools"), school_filter)

            student_filter = school_filter
            students = self._scroll_all(self._get_collection("students"), student_filter)
            total_students = sum(r.payload.get("metadata", {}).get("count", 0) for r in students)

            teacher_filter = school_filter
            teachers = self._scroll_all(self._get_collection("teachers"), teacher_filter)
            total_teachers = sum(r.payload.get("metadata", {}).get("count", 0) for r in teachers)

            ratio = round(total_students / total_teachers, 1) if total_teachers > 0 else 0

            results.append({
                "province": prov,
                "schools": len(schools),
                "students": total_students,
                "teachers": total_teachers,
                "ratio": ratio
            })

        return {
            "tool": "compare_provinces",
            "query": {"provinces": provinces, "metrics": metrics},
            "comparison": results
        }

    def _compare_years(self, year1: str, year2: str, province: str = None,
                       school_name: str = None, metric: str = "all", **kwargs) -> Dict[str, Any]:
        """Compare education data between 2 years"""
        from ..core.constants import V5_YEAR

        y1 = str(year1).strip()
        y2 = str(year2).strip()
        y1 = YEAR_ALIASES.get(y1, y1)
        y2 = YEAR_ALIASES.get(y2, y2)

        logger.info(f"📅 [CompareYears] Comparing year {y1} vs {y2}, province={province}, school={school_name}, metric={metric}")

        for y in [y1, y2]:
            if y not in AVAILABLE_YEARS:
                return {
                    "tool": "compare_years",
                    "error": f"ไม่มีข้อมูลปี {y} ในระบบ (มีเฉพาะปี {', '.join(AVAILABLE_YEARS)})",
                    "available_years": AVAILABLE_YEARS,
                }

        def get_collections_for_year(year: str) -> Dict[str, str]:
            if year == V5_YEAR:
                return COLLECTION_NAMES.copy()
            elif year in YEAR_COLLECTIONS:
                return YEAR_COLLECTIONS[year]
            else:
                return {}

        def get_year_data(year: str) -> Dict[str, Any]:
            colls = get_collections_for_year(year)
            if not colls:
                return {"error": f"ไม่มี collection สำหรับปี {year}"}

            conditions = []

            if province:
                prov = self._normalize_province(province)
                conditions.append(
                    FieldCondition(key="metadata.province", match=MatchValue(value=prov))
                )

            resolved_school_id = None
            if school_name:
                ambiguity = self._resolve_school_ambiguity(school_name, province)
                if ambiguity['type'] == 'single':
                    resolved_school_id = ambiguity['data'].payload.get('metadata', {}).get('school_id')
                elif ambiguity['type'] == 'ambiguous':
                    exact = [c for c in ambiguity['choices'] if c.get('school_name') == school_name]
                    if len(exact) == 1:
                        resolved_school_id = exact[0].get('school_id')
                    else:
                        return {
                            "ambiguous": True,
                            "choices": ambiguity['choices'],
                        }

                if resolved_school_id:
                    conditions.append(
                        FieldCondition(key="metadata.school_id", match=MatchValue(value=str(resolved_school_id)))
                    )
                elif school_name:
                    sn, _ = self._normalize_school_name(school_name)
                    conditions.append(
                        FieldCondition(key="metadata.school_name", match=MatchText(text=sn))
                    )

            scroll_filter = self._build_filter(conditions) if conditions else None

            data = {}

            if metric in ["all", "schools"]:
                try:
                    schools_coll = colls.get("schools", "")
                    if schools_coll:
                        schools = self._scroll_all(schools_coll, scroll_filter, limit=200000)
                        data["schools"] = len(schools)
                    else:
                        data["schools"] = 0
                except Exception as e:
                    logger.warning(f"⚠️ [CompareYears] Error fetching schools for {year}: {e}")
                    data["schools"] = 0

            if metric in ["all", "students", "ratio"]:
                try:
                    students_coll = colls.get("students", "")
                    if students_coll:
                        students = self._scroll_all(students_coll, scroll_filter, limit=200000)
                        total = sum(r.payload.get("metadata", {}).get("count", 0) for r in students)
                        data["students"] = total
                    else:
                        data["students"] = 0
                except Exception as e:
                    logger.warning(f"⚠️ [CompareYears] Error fetching students for {year}: {e}")
                    data["students"] = 0

            if metric in ["all", "teachers", "ratio"]:
                try:
                    teachers_coll = colls.get("teachers", "")
                    if teachers_coll:
                        teachers = self._scroll_all(teachers_coll, scroll_filter, limit=200000)
                        total = sum(r.payload.get("metadata", {}).get("count", 0) for r in teachers)
                        data["teachers"] = total
                    else:
                        data["teachers"] = 0
                except Exception as e:
                    logger.warning(f"⚠️ [CompareYears] Error fetching teachers for {year}: {e}")
                    data["teachers"] = 0

            if metric in ["all", "ratio"]:
                if data.get("teachers", 0) > 0 and data.get("students", 0) > 0:
                    data["ratio"] = round(data["students"] / data["teachers"], 1)
                else:
                    data["ratio"] = 0

            return data

        data1 = get_year_data(y1)
        data2 = get_year_data(y2)

        diff = {}
        for key in ["schools", "students", "teachers", "ratio"]:
            if key in data1 and key in data2:
                val1 = data1[key]
                val2 = data2[key]
                change = val2 - val1
                pct = round((change / val1) * 100, 1) if val1 > 0 else 0
                diff[key] = {
                    "change": change,
                    "percent_change": pct,
                    "direction": "เพิ่มขึ้น" if change > 0 else "ลดลง" if change < 0 else "เท่าเดิม"
                }

        scope = "ทั้งประเทศ"
        if school_name:
            scope = f"โรงเรียน{school_name}"
        elif province:
            scope = f"จังหวัด{province}"

        return {
            "tool": "compare_years",
            "scope": scope,
            "year1": {"year": y1, "data": data1},
            "year2": {"year": y2, "data": data2},
            "difference": diff,
            "metric": metric,
            "guidance": f"REQUIRED: สรุปการเปรียบเทียบข้อมูลปี {y1} กับ {y2} อย่างชัดเจน ระบุตัวเลข จำนวนที่เปลี่ยนแปลง และ % ที่เปลี่ยนแปลง"
        }
