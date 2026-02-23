"""
🔧 CountToolsMixin – Counting tools for teachers, students, and schools.
"""

import logging
import difflib
from typing import Dict, Any, List, Optional

from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchText, MatchAny

from ..core.constants import REGIONS

logger = logging.getLogger(__name__)


class CountToolsMixin:
    """Counting tool implementations (_count_teachers, _count_students, _count_schools)."""

    # ------------------------------------------------------------------
    # _count_teachers
    # ------------------------------------------------------------------

    def _count_teachers(self, school_name: str = None, province: str = None,
                        district: str = None, gender: str = None, person_type: str = None,
                        year: str = None, region: str = None) -> Dict[str, Any]:
        """Count teachers with various filters including person_type, year, and region"""
        logger.info(f"🔎 [CountTeachers] Called with: school={school_name}, province={province}, region={region}")

        # Detect if 'province' is actually a region name
        if province:
            if province.startswith("ภาค") or province in REGIONS:
                logger.info(f"🗺️ [CountTeachers] Province '{province}' is actually a region -> Cleaning up")
                if not region:
                    region = province
                    logger.info(f"Promoted province to region: {region}")
                province = None

        conditions = []
        resolved_school_id = None

        if school_name:
            ambiguity_check = self._resolve_school_ambiguity(school_name, province)
            if ambiguity_check['type'] == 'single':
                resolved_school_id = ambiguity_check['data'].payload.get('metadata', {}).get('school_id')
                logger.info(f"🎯 [CountTeachers] Resolved specific school ID: {resolved_school_id}")
            elif ambiguity_check['type'] == 'ambiguous':
                exact_in_choices = [c for c in ambiguity_check['choices'] if c.get('school_name') == school_name]
                if len(exact_in_choices) == 1:
                    target = exact_in_choices[0]
                    logger.info(f"🎯 [CountTeachers] Exact match found in ambiguous list. Overriding.")
                    resolved_school_id = target.get('school_id')
                else:
                    logger.info(f"🤔 [CountTeachers] Ambiguous school name '{school_name}' -> Found {len(ambiguity_check['choices'])} matches")
                    return {
                        "tool": "count_teachers",
                        "ambiguous": True,
                        "total_found": len(ambiguity_check['choices']),
                        "choices": ambiguity_check['choices'],
                        "query": {"school_name": school_name}
                    }

        conditions = []

        if resolved_school_id:
            conditions.append(
                FieldCondition(key="metadata.school_id", match=MatchValue(value=str(resolved_school_id)))
            )
        elif school_name:
            school_name, _ = self._normalize_school_name(school_name)
            conditions.append(
                FieldCondition(key="metadata.school_name", match=MatchText(text=school_name))
            )
        if province:
            province = self._normalize_province(province)
            conditions.append(
                FieldCondition(key="metadata.province", match=MatchValue(value=province))
            )
        if district:
            conditions.append(
                FieldCondition(key="metadata.district", match=MatchText(text=district))
            )
        if gender:
            conditions.append(
                FieldCondition(key="metadata.gender", match=MatchValue(value=gender))
            )
        if person_type:
            person_type = self._normalize_person_type(person_type)
            conditions.append(
                FieldCondition(key="metadata.person_type", match=MatchValue(value=person_type))
            )
        if year and not self._active_year:
            conditions.append(
                FieldCondition(key="metadata.year", match=MatchValue(value=int(year)))
            )

        # Region filter
        if region:
            region_provinces = REGIONS.get(region, [])
            if region_provinces:
                logger.info(f"🗺️ [CountTeachers] Expanding region '{region}' to {len(region_provinces)} provinces")
                province_conditions = [
                    FieldCondition(key="metadata.province", match=MatchValue(value=prov))
                    for prov in region_provinces
                ]
                conditions.append(Filter(should=province_conditions))

        scroll_filter = self._build_filter(conditions)

        # OPTIMIZATION: Use schools collection for fast total when no deep filters
        if not gender and not person_type and not school_name and not region:
            logger.info("⚡ Using Fast Ranking (Optimization) for Total Teachers")
            all_schools = self._scroll_all(self._get_collection("schools"), scroll_filter, limit=50000)

            ranked = []
            total_all = 0
            for r in all_schools:
                meta = r.payload.get("metadata", {})
                count = meta.get("total_teachers", 0)
                if count > 0:
                    ranked.append((meta.get("school_name", "Unknown"), count))
                    total_all += count

            ranked.sort(key=lambda x: x[1], reverse=True)

            top_10 = {}
            for name, count in ranked[:10]:
                top_10[name] = {"total": count}

            return {
                "tool": "count_teachers",
                "query": {"school_name": school_name, "province": province},
                "total_teachers": total_all,
                "total_found": len(ranked),
                "by_gender": {},
                "by_person_type": {},
                "by_school": top_10,
                "school_count": len(ranked)
            }

        scroll_filter = self._build_filter(conditions)
        results = self._scroll_all(self._get_collection("teachers"), scroll_filter, limit=50000,
                                   with_payload=["metadata.school_name", "metadata.count", "metadata.gender", "metadata.person_type", "metadata.province"])

        schools = {}
        by_person_type = {}
        total_count = 0
        total_male = 0
        total_female = 0

        for r in results:
            meta = r.payload.get("metadata", {})
            school = meta.get("school_name", "ไม่ระบุ")
            count = meta.get("count", 1)
            g = meta.get("gender", "-")
            pt = meta.get("person_type", "ไม่ระบุ")

            if school not in schools:
                schools[school] = {"total": 0, "male": 0, "female": 0, "province": meta.get("province")}

            schools[school]["total"] += count
            total_count += count

            if pt not in by_person_type:
                by_person_type[pt] = 0
            by_person_type[pt] += count

            if g == "ชาย":
                schools[school]["male"] += count
                total_male += count
            elif g == "หญิง":
                schools[school]["female"] += count
                total_female += count

        by_person_type = dict(sorted(by_person_type.items(), key=lambda x: x[1], reverse=True))
        is_multi_school = len(schools) > 1

        # FALLBACK: Check schools metadata
        if total_count == 0 and not person_type and not gender:
            logger.info("⚠️ No teachers found in deep stats, checking school metadata...")
            try:
                fallback_conditions = []
                if school_name:
                    sn_clean, _ = self._normalize_school_name(school_name)
                    fallback_conditions.append(FieldCondition(key="metadata.school_name", match=MatchText(text=sn_clean)))
                if province:
                    province = self._normalize_province(province)
                    fallback_conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))

                if fallback_conditions:
                    fb_filter = self._build_filter(fallback_conditions)
                    fb_results = self._scroll_all(self._get_collection("schools"), fb_filter, limit=50)

                    for r in fb_results:
                        meta = r.payload.get("metadata", {})
                        s_name = meta.get("school_name", "ไม่ระบุ")
                        s_prov = meta.get("province", "")
                        t_teachers = meta.get("total_teachers", 0)

                        if t_teachers > 0:
                            if s_name not in schools:
                                schools[s_name] = {"total": 0, "male": 0, "female": 0, "province": s_prov}
                            schools[s_name]["total"] = max(schools[s_name]["total"], t_teachers)
                            total_count += t_teachers
            except Exception as e:
                logger.error(f"❌ Fallback to schools metadata failed for teachers: {e}")

        # HYBRID ENRICHMENT
        elif total_count > 0 and school_name and len(schools) == 1:
            try:
                details = self.search_engine.get_school_details(school_name)
                if details:
                    metadata_total = details.get("total_teachers", 0)
                    if metadata_total > total_count:
                        logger.info(f"📊 HYBRID: Schools metadata has higher count ({metadata_total}) than teachers collection ({total_count})")
                        single_school_name = list(schools.keys())[0]
                        schools[single_school_name]["total"] = metadata_total
                        schools[single_school_name]["metadata_total"] = metadata_total
                        schools[single_school_name]["teachers_collection_total"] = total_count
                        total_count = metadata_total
                    elif total_count > metadata_total and metadata_total > 0:
                        logger.info(f"📊 HYBRID: Teachers collection has more data ({total_count}) than metadata ({metadata_total})")
            except Exception as e:
                logger.debug(f"Hybrid enrichment failed: {e}")

        ai_summary = f"พบข้อมูลครูทั้งหมด {total_count:,} คน"
        fallback_students_data = None

        if total_count == 0:
            ai_summary = "ไม่พบข้อมูลครูตามเงื่อนไขที่ระบุครับ"

            if school_name or resolved_school_id:
                try:
                    target_name = school_name
                    if resolved_school_id:
                        details = self.search_engine.get_school_details(resolved_school_id)
                        if details:
                            target_name = details.get('school_name')

                    if target_name:
                        logger.info(f"🔄 Fallback: Fetching student data for '{target_name}' to enrich empty teacher response")
                        fallback_data = self._count_students(school_name=target_name)

                        if fallback_data.get('total_students', 0) > 0:
                            fallback_students_data = fallback_data
                            s_count = fallback_data['total_students']
                            ai_summary = (f"ข้อมูลบุคลากรครูยังไม่ครบถ้วนในฐานข้อมูล แต่ระบบพบข้อมูล **นักเรียนทั้งหมด {s_count:,} คน** แทนครับ "
                                          f"(ระบบแนบข้อมูลนักเรียนให้แล้ว)")
                            logger.info(f"✅ Fallback successful: Attached student data ({s_count})")
                except Exception as e:
                    logger.error(f"⚠️ Smart Fallback failed: {e}")

        elif schools:
            if len(schools) <= 5:
                details_list = []
                for s, info in schools.items():
                    details_list.append(f"- {s}: {info['total']:,} คน")
                ai_summary += "\n" + "\n".join(details_list)
            else:
                ai_summary += f" (กระจายอยู่ใน {len(schools)} โรงเรียน)"

        # person_type correction
        if person_type and by_person_type:
            filtered_total = by_person_type.get(person_type, 0)
            if filtered_total > 0 and filtered_total != total_count:
                logger.info(f"🔧 [CountTeachers] Correcting total from {total_count} → {filtered_total} (person_type={person_type})")
                total_count = filtered_total
                total_male = 0
                total_female = 0
                for r in results:
                    meta = r.payload.get("metadata", {})
                    pt = meta.get("person_type", "ไม่ระบุ")
                    if pt == person_type:
                        count = meta.get("count", 1)
                        g = meta.get("gender", "-")
                        if g == "ชาย":
                            total_male += count
                        elif g == "หญิง":
                            total_female += count

        logger.info(f"📊 [CountTeachers] total_count={total_count}, male={total_male}, female={total_female}, person_type={person_type}, by_person_type={by_person_type}")

        if person_type:
            ai_summary = f"พบข้อมูล{person_type}ทั้งหมด {total_count:,} คน"

        result = {
            "tool": "count_teachers",
            "query": {"school_name": school_name, "province": province, "gender": gender, "person_type": person_type, "region": region},
            "total_teachers": total_count,
            "total_found": len(schools),
            "by_gender": {"male": total_male, "female": total_female},
            "ai_summary": ai_summary,
            "by_person_type": by_person_type,
            "by_school": dict(sorted(schools.items(), key=lambda x: x[1]['total'], reverse=True)[:10]),
            "school_count": len(schools),
            "is_multi_school": is_multi_school,
            "fallback_students": fallback_students_data,
            "data_missing": (fallback_students_data is not None)
        }

        if total_count == 0 and school_name:
            suggestions = self._suggest_schools(school_name)
            if suggestions:
                result["found"] = False
                result["suggestions"] = suggestions

        return result

    # ------------------------------------------------------------------
    # _count_students
    # ------------------------------------------------------------------

    def _count_students(self, school_name: str = None, province: str = None,
                        district: str = None, grade: str = None,
                        gender: str = None, year: str = None,
                        agency: str = None, **kwargs) -> Dict[str, Any]:
        """Count students with various filters including year"""
        resolved_school_id = None

        if school_name:
            ambiguity_check = self._resolve_school_ambiguity(school_name, province)
            if ambiguity_check['type'] == 'single':
                resolved_school_id = ambiguity_check['data'].payload.get('metadata', {}).get('school_id')
                logger.info(f"🎯 Resolved specific school ID: {resolved_school_id}")
            elif ambiguity_check['type'] == 'ambiguous':
                exact_in_choices = [c for c in ambiguity_check['choices'] if c.get('school_name') == school_name]
                if len(exact_in_choices) == 1:
                    target = exact_in_choices[0]
                    logger.info(f"🎯 Exact match '{school_name}' found in ambiguous list. Overriding.")
                    resolved_school_id = target.get('school_id')
                else:
                    logger.info(f"🤔 Ambiguous school name '{school_name}' -> Found {len(ambiguity_check['choices'])} matches")
                    return {
                        "tool": "count_students",
                        "ambiguous": True,
                        "total_students": 0,
                        "total_found": len(ambiguity_check['choices']),
                        "choices": ambiguity_check['choices'],
                        "query": {"school_name": school_name}
                    }

        conditions = []

        if resolved_school_id:
            conditions.append(
                FieldCondition(key="metadata.school_id", match=MatchValue(value=str(resolved_school_id)))
            )
        elif school_name:
            school_name, extracted_grade = self._normalize_school_name(school_name)
            conditions.append(
                FieldCondition(key="metadata.school_name", match=MatchText(text=school_name))
            )
            if not grade and extracted_grade:
                grade = extracted_grade

        if province and not resolved_school_id:
            province = self._normalize_province(province)
            conditions.append(
                FieldCondition(key="metadata.province", match=MatchValue(value=province))
            )

        # Region from kwargs
        region = kwargs.get('region')
        if region and not province and not resolved_school_id:
            region_provinces = REGIONS.get(region, [])
            if region_provinces:
                logger.info(f"Adding Region Filter: {region} ({len(region_provinces)} provinces)")
                conditions.append(
                    Filter(should=[
                        FieldCondition(key="metadata.province", match=MatchValue(value=p))
                        for p in region_provinces
                    ])
                )

        if district:
            conditions.append(
                FieldCondition(key="metadata.district", match=MatchText(text=district))
            )
        if grade:
            grade = self._normalize_grade(grade)
            if grade == "อนุบาล":
                conditions.append(
                    Filter(
                        should=[
                            FieldCondition(key="metadata.grade", match=MatchText(text="อนุบาล")),
                            FieldCondition(key="metadata.grade", match=MatchText(text="ปฐมวัย")),
                            FieldCondition(key="metadata.grade", match=MatchValue(value="อ.1")),
                            FieldCondition(key="metadata.grade", match=MatchValue(value="อ.2")),
                            FieldCondition(key="metadata.grade", match=MatchValue(value="อ.3")),
                        ]
                    )
                )
            elif grade:
                conditions.append(
                    FieldCondition(key="metadata.grade", match=MatchText(text=grade))
                )
        if gender:
            conditions.append(
                FieldCondition(key="metadata.gender", match=MatchValue(value=gender))
            )
        if year and not self._active_year:
            conditions.append(
                FieldCondition(key="metadata.year", match=MatchValue(value=int(year)))
            )

        scroll_filter = self._build_filter(conditions)

        # OPTIMIZATION: Fast path when no deep filters
        if not grade and not gender and not school_name and (not year or self._active_year):
            try:
                logger.info("⚡ Using Fast Ranking (Optimization) for Total Students")
                all_schools = self._scroll_all(self._get_collection("schools"), scroll_filter, limit=50000)

                ranked = []
                total_all = 0
                for r in all_schools:
                    meta = r.payload.get("metadata", {})
                    count = meta.get("total_students", 0)
                    if count > 0:
                        ranked.append((meta.get("school_name", "Unknown"), count))
                        total_all += count

                ranked.sort(key=lambda x: x[1], reverse=True)

                top_10 = {}
                for name, count in ranked[:10]:
                    top_10[name] = {"total": count}

                by_gender = {"male": 0, "female": 0}
                by_grade = {}

                try:
                    student_results = self._scroll_all(self._get_collection("students"), scroll_filter, limit=50000,
                                                       with_payload=["metadata.count", "metadata.gender", "metadata.grade"])

                    for r in student_results:
                        meta = r.payload.get("metadata", {})
                        count = meta.get("count", 1)
                        g = meta.get("gender", "-")
                        grade_val = meta.get("grade", "ไม่ระบุ")

                        if g == "ชาย":
                            by_gender["male"] += count
                        elif g == "หญิง":
                            by_gender["female"] += count

                        if grade_val not in by_grade:
                            by_grade[grade_val] = {"total": 0, "male": 0, "female": 0}
                        by_grade[grade_val]["total"] += count
                        if g == "ชาย":
                            by_grade[grade_val]["male"] += count
                        elif g == "หญิง":
                            by_grade[grade_val]["female"] += count

                    logger.info(f"📊 Province breakdown: {len(by_grade)} grades, {by_gender['male']} male, {by_gender['female']} female")
                except Exception as e:
                    logger.warning(f"⚠️ Could not fetch grade/gender breakdown: {e}")

                return {
                    "tool": "count_students",
                    "query": {"school_name": school_name, "province": province},
                    "total_students": total_all,
                    "by_gender": by_gender,
                    "by_school": top_10,
                    "school_count": len(ranked),
                    "student_breakdown": by_grade,
                    "student_breakdown_source": "edu_students_v5" if by_grade else None,
                    "ambiguous_schools": []
                }
            except Exception as e:
                logger.error(f"❌ OPTIMIZATION CRASHED: {e}")
                import traceback
                logger.error(traceback.format_exc())

        # Full aggregation path
        results = self._scroll_all(self._get_collection("students"), scroll_filter, limit=50000,
                                   with_payload=["metadata.school_name", "metadata.count", "metadata.gender", "metadata.province"])

        schools = {}
        total_count = 0
        total_male = 0
        total_female = 0

        target_name = school_name.replace(" ", "") if school_name else None

        for r in results:
            meta = r.payload.get("metadata", {})
            school = meta.get("school_name", "ไม่ระบุ")

            count = meta.get("count", 1)
            g = meta.get("gender", "-")

            if school not in schools:
                schools[school] = {"total": 0, "male": 0, "female": 0, "province": meta.get("province")}

            schools[school]["total"] += count
            total_count += count

            if g == "ชาย":
                schools[school]["male"] += count
                total_male += count
            elif g == "หญิง":
                schools[school]["female"] += count
                total_female += count

        is_multi_school = len(schools) > 1

        # SMART REDUCTION: exact match from ambiguous list
        if is_multi_school and school_name:
            exact_matches = [s for s in schools.keys() if s == school_name]

            if not exact_matches:
                target_clean, _ = self._normalize_school_name(school_name)
                exact_matches = [s for s in schools.keys() if self._normalize_school_name(s)[0] == target_clean]

            if len(exact_matches) == 1:
                target = exact_matches[0]
                logger.info(f"🎯 Exact match found in ambiguous list: '{target}'. Ignoring others.")
                schools = {target: schools[target]}
                total_count = schools[target]['total']
                total_male = schools[target]['male']
                total_female = schools[target]['female']
                is_multi_school = False

        # SUPER FALLBACK via direct fetch
        if is_multi_school and school_name:
            try:
                details = self.search_engine.get_school_details(school_name)
                if details:
                    logger.info(f"🎯 Direct fetch found exact match for '{school_name}', overriding ambiguous list.")
                    s_name = details['school_name']
                    t_students = details.get('total_students', 0)
                    schools = {s_name: {"total": t_students, "male": 0, "female": 0, "province": details.get('province', '')}}
                    total_count = t_students
                    is_multi_school = False
            except Exception as e:
                logger.error(f"Fallback fetch failed: {e}")

        # FALLBACK: Check schools metadata
        if total_count == 0 and not grade and not gender and not year:
            logger.info("⚠️ No students found in deep stats, checking school metadata...")
            try:
                fallback_conditions = []
                if school_name:
                    sn_clean, _ = self._normalize_school_name(school_name)
                    fallback_conditions.append(FieldCondition(key="metadata.school_name", match=MatchText(text=sn_clean)))
                if province:
                    province = self._normalize_province(province)
                    fallback_conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))
                if district:
                    fallback_conditions.append(FieldCondition(key="metadata.district", match=MatchText(text=district)))

                if fallback_conditions:
                    fb_filter = self._build_filter(fallback_conditions)
                    fb_results = self._scroll_all(self._get_collection("schools"), fb_filter, limit=50)

                    for r in fb_results:
                        meta = r.payload.get("metadata", {})
                        s_name = meta.get("school_name", "ไม่ระบุ")
                        s_prov = meta.get("province", "")
                        t_students = meta.get("total_students", 0)

                        if t_students > 0:
                            if s_name not in schools:
                                schools[s_name] = {"total": 0, "male": 0, "female": 0, "province": s_prov}
                            schools[s_name]["total"] = max(schools[s_name]["total"], t_students)
                            total_count += t_students
            except Exception as e:
                logger.error(f"❌ Fallback to schools metadata failed: {e}")

        result = {
            "tool": "count_students",
            "query": {"school_name": school_name, "province": province, "grade": grade, "gender": gender},
            "total_students": total_count,
            "by_gender": {"male": total_male, "female": total_female},
            "by_school": dict(sorted(schools.items(), key=lambda x: x[1]['total'], reverse=True)[:20]),
            "school_count": len(schools),
            "is_multi_school": is_multi_school
        }

        # ENHANCEMENT: detailed breakdown for single school
        if len(schools) == 1:
            try:
                single_school_name = list(schools.keys())[0]
                school_id = None

                for r in results:
                    meta = r.payload.get("metadata", {})
                    if meta.get("school_name") == single_school_name:
                        school_id = meta.get("school_id")
                        break

                if not school_id and school_name:
                    details = self.search_engine.get_school_details(single_school_name)
                    if details:
                        school_id = details.get("school_id")

                if school_id:
                    stats = self.search_engine.get_student_statistics(school_id)
                    if stats:
                        result["student_breakdown"] = stats.get("by_grade", {})
                        result["student_breakdown_source"] = stats.get("source")
                        logger.info(f"📊 Attached student breakdown to count_students for {single_school_name}")
            except Exception as e:
                logger.error(f"❌ Failed to attach student breakdown in count_students: {e}")

        # SMART GRADE FALLBACK
        if total_count == 0 and grade and school_name:
            try:
                logger.info(f"🔍 Grade fallback: re-querying '{school_name}' without grade filter...")

                fallback_conditions = []
                if resolved_school_id:
                    fallback_conditions.append(
                        FieldCondition(key="metadata.school_id", match=MatchValue(value=str(resolved_school_id)))
                    )
                elif school_name:
                    sn_clean, _ = self._normalize_school_name(school_name)
                    fallback_conditions.append(
                        FieldCondition(key="metadata.school_name", match=MatchText(text=sn_clean))
                    )
                if province:
                    fallback_conditions.append(
                        FieldCondition(key="metadata.province", match=MatchValue(value=province))
                    )

                fb_filter = self._build_filter(fallback_conditions)
                fb_results = self._scroll_all(
                    self._get_collection("students"), fb_filter, limit=5000,
                    with_payload=["metadata.grade", "metadata.count", "metadata.school_name"]
                )

                available_grades = {}
                total_no_grade = 0
                for r in fb_results:
                    meta = r.payload.get("metadata", {})
                    g = meta.get("grade", "")
                    count = meta.get("count", 0)
                    if g:
                        available_grades[g] = available_grades.get(g, 0) + count
                    total_no_grade += count

                if available_grades:
                    logger.info(f"📚 School '{school_name}' offers grades: {list(available_grades.keys())}")
                    result["grade_not_found"] = True
                    result["requested_grade"] = grade
                    result["available_grades"] = available_grades
                    result["total_students_all_grades"] = total_no_grade
                    result["ai_summary"] = (
                        f"โรงเรียน{school_name} ไม่มีชั้น {grade} ในระบบ "
                        f"โรงเรียนนี้เปิดสอนระดับ: {', '.join(available_grades.keys())} "
                        f"มีนักเรียนรวมทั้งหมด {total_no_grade:,} คน"
                    )
            except Exception as e:
                logger.error(f"❌ Grade fallback query failed: {e}")

        # FUZZY SUGGESTION FALLBACK
        if total_count == 0 and school_name and not result.get("grade_not_found"):
            suggestions = self._suggest_schools(school_name)
            if suggestions:
                result["found"] = False
                result["suggestions"] = suggestions

        return result

    # ------------------------------------------------------------------
    # _count_schools
    # ------------------------------------------------------------------

    def _count_schools(self, province: str = None, district: str = None,
                       subdistrict: str = None, agency: str = None, region: str = None, **kwargs) -> Dict[str, Any]:
        """Count schools in an area including subdistrict and region"""
        if province:
            province = province.strip()
        if region:
            region = region.strip()

        # Detect if "province" accidentally contains a region name
        if province and not region and (province.startswith("ภาค") or province in REGIONS):
            logger.info(f"🗺️ [CountSchools] Province param is region -> promote to region: '{province}'")
            region = province
            province = None

        agency_norm = self._normalize_agency(agency) if agency else None
        province_norm = self._normalize_province(province) if province else None

        def _build_conditions(pv, dist, subdist, reg):
            conds = []
            if reg:
                region_provinces = REGIONS.get(reg, [])
                if region_provinces:
                    conds.append(
                        Filter(should=[
                            FieldCondition(key="metadata.province", match=MatchValue(value=prov))
                            for prov in region_provinces
                        ])
                    )
            elif pv:
                conds.append(FieldCondition(key="metadata.province", match=MatchValue(value=pv)))
            if dist:
                conds.append(FieldCondition(key="metadata.district", match=MatchText(text=dist)))
            if subdist:
                conds.append(FieldCondition(key="metadata.subdistrict", match=MatchText(text=subdist)))
            if agency_norm:
                conds.append(FieldCondition(key="metadata.agency", match=MatchValue(value=agency_norm)))
            return conds

        def _aggregate(rows):
            unique_keys = set()
            by_agency = {}
            by_district = {}
            total_students_all = 0
            total_teachers_all = 0

            for r in rows:
                meta = r.payload.get("metadata", {})
                sid = meta.get("school_id")
                name = meta.get("school_name", "ไม่ระบุ")
                key = sid if sid else f"{name}_{meta.get('province', '')}"
                if key in unique_keys:
                    continue
                unique_keys.add(key)

                agency_name = meta.get("agency", "ไม่ระบุ")
                by_agency[agency_name] = by_agency.get(agency_name, 0) + 1

                district_name = meta.get("district", "ไม่ระบุ")
                by_district[district_name] = by_district.get(district_name, 0) + 1

                total_students_all += meta.get("total_students", 0) or 0
                total_teachers_all += meta.get("total_teachers", 0) or 0

            sorted_districts = dict(sorted(by_district.items(), key=lambda x: x[1], reverse=True)[:10])
            return {
                "total_schools": len(unique_keys),
                "total_students": total_students_all,
                "total_teachers": total_teachers_all,
                "by_agency": by_agency,
                "by_district": sorted_districts if sorted_districts else None,
            }

        def _query_rows(pv, dist, subdist, reg):
            scroll_filter = self._build_filter(_build_conditions(pv, dist, subdist, reg))
            return self._scroll_all(
                self._get_collection("schools"),
                scroll_filter,
                limit=20000,
                with_payload=[
                    "metadata.school_id",
                    "metadata.school_name",
                    "metadata.province",
                    "metadata.agency",
                    "metadata.district",
                    "metadata.total_students",
                    "metadata.total_teachers",
                ],
            )

        rows = _query_rows(province_norm, district, subdistrict, region)
        stats = _aggregate(rows)
        ai_summary = None

        # Self-healing: retry with broader scope
        if stats["total_schools"] == 0 and (district or subdistrict):
            if subdistrict:
                broader_rows = _query_rows(province_norm, district, None, region)
                broader_stats = _aggregate(broader_rows)
                if broader_stats["total_schools"] > 0:
                    stats = broader_stats
                    ai_summary = (
                        f"ไม่พบข้อมูลตำบล/แขวง '{subdistrict}' ตามเงื่อนไขที่ระบุครับ "
                        f"แต่พบข้อมูลในระดับอำเภอ '{district}' จำนวน {stats['total_schools']:,} โรงเรียน"
                    )

            if stats["total_schools"] == 0 and district:
                broader_rows = _query_rows(province_norm, None, None, region)
                broader_stats = _aggregate(broader_rows)
                if broader_stats["total_schools"] > 0:
                    stats = broader_stats
                    scope_text = f"จังหวัด{province_norm}" if province_norm else (region or "พื้นที่ที่เกี่ยวข้อง")
                    ai_summary = (
                        f"ไม่พบข้อมูลอำเภอ/เขต '{district}' ใน{scope_text} ครับ "
                        f"แต่พบข้อมูล{scope_text}รวม {stats['total_schools']:,} โรงเรียน"
                    )
                    district_pool = list((broader_stats.get("by_district") or {}).keys())
                    if district_pool:
                        ranked = sorted(
                            district_pool,
                            key=lambda name: difflib.SequenceMatcher(a=district, b=name).ratio(),
                            reverse=True,
                        )
                        candidates = [name for name in ranked[:3] if name and difflib.SequenceMatcher(a=district, b=name).ratio() >= 0.5]
                        if candidates:
                            ai_summary += f" (ชื่ออำเภอที่ใกล้เคียง: {', '.join(candidates)})"

        return {
            "tool": "count_schools",
            "query": {
                "province": province_norm,
                "district": district,
                "subdistrict": subdistrict,
                "agency": agency_norm,
                "region": region,
            },
            "total_schools": stats["total_schools"],
            "total_students": stats["total_students"],
            "total_teachers": stats["total_teachers"],
            "by_agency": stats["by_agency"],
            "by_district": stats["by_district"],
            "ai_summary": ai_summary,
        }
