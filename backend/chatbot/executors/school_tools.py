"""
🔧 SchoolToolsMixin – School search, list, filter, details, nearby, and suggestions.
"""

import logging
import difflib
from typing import Dict, Any, List, Optional, Tuple

from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchText, MatchAny
from qdrant_client import models

from ..core.constants import REGIONS

logger = logging.getLogger(__name__)


class SchoolToolsMixin:
    """School-related tool implementations (search, list, filter, details)."""

    # ------------------------------------------------------------------
    # Disambiguation / search helpers
    # ------------------------------------------------------------------

    def _resolve_school_ambiguity(self, school_name: str, province: str = None, district: str = None) -> Dict[str, Any]:
        """
        Helper to check if a school name implies multiple matches.
        Returns: 
           - {'type': 'single', 'data': school_obj}
           - {'type': 'ambiguous', 'choices': [list of schools]}
           - {'type': 'not_found'}
        """
        matches = self._smart_search_school(school_name, province, limit=20)

        # FALLBACK: If not found in the specific province, try GLOBAL search
        if not matches and province:
            logger.info(f"🔄 Disambiguation: '{school_name}' not found in '{province}', trying global search...")
            matches = self._smart_search_school(school_name, province=None, limit=20)

        if not matches:
            return {'type': 'not_found'}

        clean_input = self._clean_search_query(school_name).replace("โรงเรียน", "").strip()

        # If district is specified, filter matches by district first
        if district:
            district_clean = district.replace("เขต", "").replace("อำเภอ", "").strip()
            filtered = [m for m in matches
                       if district_clean in (m.payload.get('metadata', {}).get('district', '') or '')]
            if filtered:
                matches = filtered
                logger.info(f"📋 District filter '{district_clean}' narrowed to {len(matches)} matches")

        unique_names = {}
        for m in matches:
            meta = m.payload.get('metadata', {})
            name = meta.get('school_name', '')
            dist = meta.get('district', '')
            prov = meta.get('province', '')
            key = f"{name}_{prov}"
            if key not in unique_names:
                unique_names[key] = {
                    "school_name": name,
                    "district": dist,
                    "province": prov,
                    "school_id": meta.get('school_id'),
                    "total_students": meta.get('total_students', 0),
                    "total_teachers": meta.get('total_teachers', 0)
                }

        unique_list = list(unique_names.values())

        if len(unique_list) == 1:
            return {'type': 'single', 'data': matches[0]}

        return {'type': 'ambiguous', 'choices': unique_list}

    def _smart_search_school(self, school_name: str, province: str = None, limit: int = 5) -> List[Any]:
        """Hybrid search strategy: Exact -> Prefix -> Fuzzy"""
        results = []
        found_ids = set()

        queries_to_try = []
        if school_name:
            cleaned_school_name = self._clean_search_query(school_name)
            logger.info(f"🧹 Query Cleaning: '{school_name}' -> '{cleaned_school_name}'")
            school_name = cleaned_school_name

            school_name = self._thai_to_arabic_numerals(school_name)
            clean_name = school_name.replace("ร.ร.", "").replace("รร.", "").replace("รร", "").replace("โรงเรียน", "").strip()

            queries_to_try.append(clean_name)

            if school_name != clean_name and school_name not in queries_to_try:
                queries_to_try.append(school_name)

            queries_to_try.append(f"โรงเรียน{clean_name}")

            suffixes = ["วิทยาลัย", "ศึกษา", "วิทยา", "พัฒนาการ"]
            for suffix in suffixes:
                if not clean_name.endswith(suffix):
                    queries_to_try.append(f"{clean_name}{suffix}")

            queries_to_try.insert(0, {"type": "exact", "value": clean_name})
        else:
            queries_to_try = [None]

        logger.info(f"🔍 Smart Search Pattern: {queries_to_try}")

        for query in queries_to_try:
            if len(results) >= limit:
                break

            conditions = []
            if query:
                if isinstance(query, dict) and query.get("type") == "exact":
                    conditions.append(FieldCondition(key="metadata.school_name", match=MatchValue(value=query["value"])))
                else:
                    conditions.append(FieldCondition(key="metadata.school_name", match=MatchText(text=query)))
            if province:
                p_norm = self._normalize_province(province)
                conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=p_norm)))

            scroll_filter = self._build_filter(conditions)
            batch = self._scroll_all(self._get_collection("schools"), scroll_filter, limit=limit)

            for res in batch:
                sid = res.payload.get('metadata', {}).get('school_id')
                if sid and sid not in found_ids:
                    results.append(res)
                    found_ids.add(sid)

        # Fallback: Semantic/Vector Search
        if len(results) < limit:
            logger.info("⚠️ Exact match insufficient, falling back to Semantic Search...")
            try:
                from ..search.search_engine import SearchEngine

                engine = SearchEngine(self.client, llm_provider=self.llm_provider)

                semantic_filter = None
                if province:
                    p_norm = self._normalize_province(province)
                    semantic_filter = Filter(must=[
                        FieldCondition(key="metadata.province", match=MatchValue(value=p_norm))
                    ])

                semantic_results = engine._semantic_search(
                    query=school_name,
                    collection_name=self._get_collection("schools"),
                    top_k=limit - len(results),
                    filters=semantic_filter
                )

                if semantic_results:
                    logger.info(f"🧠 Semantic Search found {len(semantic_results)} results")
                    for res in semantic_results:
                        if res.score < 0.65:
                            continue
                        sid = res.payload.get('metadata', {}).get('school_id')
                        if sid and sid not in found_ids:
                            results.append(res)
                            found_ids.add(sid)
            except Exception as e:
                logger.error(f"❌ Semantic search fallback failed: {e}")

        return results

    def _suggest_schools(self, school_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Find similar school names when exact search fails"""
        if not school_name:
            return []

        suggestions = []
        seen = set()

        clean_name = self._thai_to_arabic_numerals(school_name)
        clean_name = clean_name.replace("โรงเรียน", "").replace("รร.", "").strip()

        if len(clean_name) < 2:
            return []

        keywords = clean_name.split()
        search_terms = []
        if keywords:
            search_terms.append(keywords[0])

        if len(clean_name) > 4:
            search_terms.append(clean_name[:4])

        if len(clean_name) >= 3:
            search_terms.append(clean_name[:2]) if len(clean_name) < 5 else search_terms.append(clean_name[:3])

        for term in search_terms:
            if len(suggestions) >= limit:
                break

            condition = FieldCondition(key="metadata.school_name", match=MatchText(text=term))
            results = self._scroll_all(self._get_collection("schools"), self._build_filter([condition]), limit=20)

            for r in results:
                meta = r.payload.get("metadata", {})
                name = meta.get("school_name", "")
                if name and name not in seen:
                    seen.add(name)
                    suggestions.append({
                        "name": name,
                        "province": meta.get("province"),
                        "school_id": meta.get("school_id")
                    })
                    if len(suggestions) >= limit:
                        break

        return suggestions

    def _normalize_school_name(self, name: str) -> Tuple[str, str]:
        """Remove common prefixes and extract grade if embedded in name"""
        if not name:
            return name, None

        import re

        name = self._thai_to_arabic_numerals(name)

        prefixes_to_remove = [
            "โรงเรียน", "รร.", "ร.ร.", "รร", "วิทยาลัย", "โรง", "ศูนย์การศึกษา"
        ]
        for prefix in prefixes_to_remove:
            if name.startswith(prefix):
                name = name[len(prefix):]
                break

        name = name.strip()
        extracted_grade = None

        grade_patterns = [
            (r'(ระดับ)?ประกาศนียบัตรวิชาชีพ(ชั้นสูง)?ปีที่\s*(\d+)', lambda m: f"ปวส.{m.group(3)}" if m.group(2) else f"ปวช.{m.group(3)}"),
            (r'(ระดับ)?ปวช\.?\s*(\d+)', lambda m: f"ปวช.{m.group(2)}"),
            (r'(ระดับ)?ปวส\.?\s*(\d+)', lambda m: f"ปวส.{m.group(2)}"),
            (r'(ระดับ)?ชั้น?มัธยมศึกษาปีที่\s*(\d+)', lambda m: f"ม.{m.group(2)}"),
            (r'(ระดับ)?ชั้น?ม\.?\s*(\d+)', lambda m: f"ม.{m.group(2)}"),
            (r'(ระดับ)?ชั้น?ประถมศึกษาปีที่\s*(\d+)', lambda m: f"ป.{m.group(2)}"),
            (r'(ระดับ)?ชั้น?ป\.?\s*(\d+)', lambda m: f"ป.{m.group(2)}"),
            (r'(ระดับ)?ชั้น?อนุบาล\s*(\d+)?', lambda m: f"อนุบาล{m.group(2) or ''}"),
        ]

        for pattern, extractor in grade_patterns:
            match = re.search(pattern, name)
            if match:
                extracted_grade = extractor(match)
                name = re.sub(pattern + r'.*$', '', name)
                break

        name = re.sub(r'(ระดับ)?ชั้น.*$', '', name)

        return name.strip(), extracted_grade

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def _search_schools(self, school_name: str = None, province: str = None,
                        district: str = None, subdistrict: str = None, agency: str = None, region: str = None,
                        metric: str = None, limit: int = 10, **kwargs) -> Dict[str, Any]:
        """Search for schools with various filters, supporting extra params like grade"""
        grade_param = kwargs.get('grade')
        if not school_name and grade_param:
            logger.info(f"💡 Using extracted grade '{grade_param}' as school_name for semantic search")
            school_name = grade_param

        original_school_name = school_name
        actual_total_count = 0

        count_conditions = []
        if school_name:
            clean_name = self._thai_to_arabic_numerals(school_name)
            if "โรงเรียน" in clean_name or "รร" in clean_name:
                clean_name = clean_name.replace("ร.ร.", "").replace("รร.", "").replace("รร", "").replace("โรงเรียน", "").strip()
            pass

        if province:
            count_conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=self._normalize_province(province))))

        if region and not province:
            target_provinces = REGIONS.get(region, [])
            if target_provinces:
                logger.info(f"📍 Filtering by Region: {region} -> {len(target_provinces)} provinces")
                count_conditions.append(FieldCondition(key="metadata.province", match=MatchAny(any=target_provinces)))
            else:
                logger.warning(f"⚠️ Region '{region}' not found or empty")
        if district:
            district_clean = district.replace('อำเภอ', '').replace('อ.', '').replace('เขต', '').strip()
            count_conditions.append(FieldCondition(key="metadata.district", match=MatchText(text=district_clean)))
        if agency:
            count_conditions.append(FieldCondition(key="metadata.agency", match=MatchText(text=self._normalize_agency(agency))))
        if subdistrict:
            count_conditions.append(FieldCondition(key="metadata.subdistrict", match=MatchText(text=subdistrict)))

        if count_conditions:
            count_filter = self._build_filter(count_conditions)
            actual_total_count = self._count_filtered(self._get_collection("schools"), count_filter)
        else:
            actual_total_count = self._count_filtered(self._get_collection("schools"), None)

        if actual_total_count == 0:
            if subdistrict or district:
                suggestion = self._get_fuzzy_suggestion(subdistrict, province, district)
                if suggestion:
                    return {"tool": "search_schools", "found": False, "total_found": 0, "results": [], "ai_summary": suggestion}

            return {"tool": "search_schools", "found": False, "total_found": 0, "results": []}

        if school_name and not district and not agency:
            fetch_limit = 50
            results = self._smart_search_school(original_school_name, province, limit=fetch_limit)
            actual_total_count = len(results)
            if len(results) > int(limit):
                results = results[:int(limit)]
                if actual_total_count >= fetch_limit:
                    actual_total_count = f"{fetch_limit}+"
        else:
            results = self._scroll_all(self._get_collection("schools"), count_filter if count_conditions else None, limit=int(limit))

        formatted = []
        for r in results:
            meta = r.payload.get("metadata", {}) if hasattr(r, "payload") else r
            item = {
                "school_name": meta.get("school_name"),
                "province": meta.get("province"),
                "district": meta.get("district"),
                "total_students": meta.get("total_students"),
                "total_teachers": meta.get("total_teachers"),
                "agency": meta.get("agency")
            }

            if metric == "students":
                if "total_teachers" in item:
                    del item["total_teachers"]
            elif metric == "teachers":
                if "total_students" in item:
                    del item["total_students"]

            formatted.append(item)

        if not metric and formatted:
            all_no_students = all(not item.get("total_students") for item in formatted)
            all_no_teachers = all(not item.get("total_teachers") for item in formatted)

            if all_no_students or all_no_teachers:
                logger.info(f"🧹 Auto-Pruning: Students={all_no_students}, Teachers={all_no_teachers}")
                for item in formatted:
                    if all_no_students and "total_students" in item:
                        del item["total_students"]
                    if all_no_teachers and "total_teachers" in item:
                        del item["total_teachers"]

        suggestions = []
        if len(formatted) == 0 and original_school_name:
            logger.info(f"🤔 No results for '{original_school_name}', trying suggestions...")
            suggestions = self._suggest_schools(original_school_name)

        ai_summary = f"พบโรงเรียนทั้งหมด {actual_total_count} แห่ง แต่แสดงผลเพียง {len(formatted)} แห่ง"
        if actual_total_count == len(formatted):
            ai_summary = f"พบโรงเรียนทั้งหมด {actual_total_count} แห่ง (แสดงครบแล้ว)"

        return {
            "tool": "search_schools",
            "found": len(formatted) > 0,
            "total_found": actual_total_count,
            "results": formatted,
            "suggestions": suggestions,
            "ai_summary": ai_summary
        }

    def _advanced_school_search(self, province: str = None, district: str = None,
                                min_students: int = None, max_students: int = None,
                                min_teachers: int = None, max_teachers: int = None,
                                agency: str = None, limit: int = 10) -> Dict[str, Any]:
        """Advanced search with numeric ranges and multiple criteria."""
        filters = {
            'province': self._normalize_province(province) if province else None,
            'district': district,
            'agency': self._normalize_agency(agency) if agency else None,
            'min_students': min_students,
            'max_students': max_students,
            'min_teachers': min_teachers,
            'max_teachers': max_teachers
        }
        filters = {k: v for k, v in filters.items() if v is not None}

        logger.info(f"🔬 Advanced Search Params: {filters}")

        results, total_count, _ = self.search_engine.search_by_criteria(filters, limit=limit)

        formatted = []
        for point in results:
            meta = point.payload.get('metadata', {})
            formatted.append({
                "school_name": meta.get("school_name"),
                "province": meta.get("province"),
                "district": meta.get("district"),
                "total_students": meta.get("total_students"),
                "total_teachers": meta.get("total_teachers"),
                "agency": meta.get("agency")
            })

        ai_summary = f"พบตามเงื่อนไขทั้งหมด {total_count} แห่ง แต่แสดงผลเพียง {len(formatted)} แห่ง"
        if total_count == len(formatted):
            ai_summary = f"พบตามเงื่อนไขทั้งหมด {total_count} แห่ง (แสดงครบแล้ว)"

        return {
            "tool": "advanced_school_search",
            "query": filters,
            "total_found": total_count,
            "count": len(formatted),
            "results": formatted,
            "ai_summary": ai_summary
        }

    def _list_schools(self, province: str = None, district: str = None,
                      subdistrict: str = None, agency: str = None, limit: int = 10, **kwargs) -> Dict[str, Any]:
        """List schools in an area"""
        return self._search_schools(province=province, district=district, subdistrict=subdistrict,
                                    agency=agency, limit=limit)

    def _filter_schools(self, metric: str, operator: str, value: int,
                        province: str = None, district: str = None,
                        subdistrict: str = None, region: str = None, limit: int = 20, **kwargs) -> Dict[str, Any]:
        """Filter schools by numeric threshold (e.g., schools with < 100 students)"""
        operator = operator.lower().strip()

        operator_aliases = {
            "less_than": "lt", "<": "lt", "lessthan": "lt",
            "greater_than": "gt", ">": "gt", "greaterthan": "gt",
            "equal": "eq", "equals": "eq", "==": "eq", "=": "eq",
            "less_than_or_equal": "lte", "<=": "lte",
            "greater_than_or_equal": "gte", ">=": "gte",
        }
        operator = operator_aliases.get(operator, operator)

        value = int(value)

        conditions = []
        if region:
            region_provinces = REGIONS.get(region, [])
            if region_provinces:
                conditions.append(
                    Filter(should=[
                        FieldCondition(key="metadata.province", match=MatchValue(value=p))
                        for p in region_provinces
                    ])
                )
        elif province:
            province = self._normalize_province(province)
            conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))
        if district:
            conditions.append(FieldCondition(key="metadata.district", match=MatchText(text=district)))
        if subdistrict:
            conditions.append(FieldCondition(key="metadata.subdistrict", match=MatchText(text=subdistrict)))

        scroll_filter = self._build_filter(conditions) if conditions else None

        SCROLL_CAP = 10000
        all_schools = self._scroll_all(self._get_collection("schools"), scroll_filter, limit=SCROLL_CAP)
        capped = len(all_schools) >= SCROLL_CAP
        logger.info(f"DEBUG: _filter_schools fetched {len(all_schools)} schools from DB{' (CAPPED!)' if capped else ''}")

        if metric.lower() in ["students", "student", "นักเรียน"]:
            field_name = "total_students"
        elif metric.lower() in ["teachers", "teacher", "ครู", "บุคลากร"]:
            field_name = "total_teachers"
        else:
            field_name = "total_students"

        matching_schools = []
        for r in all_schools:
            meta = r.payload.get("metadata", {})
            count = meta.get(field_name, 0) or 0

            matches = False
            if operator == "lt" and count < value:
                matches = True
            elif operator == "gt" and count > value:
                matches = True
            elif operator == "eq" and count == value:
                matches = True
            elif operator == "lte" and count <= value:
                matches = True
            elif operator == "gte" and count >= value:
                matches = True

            if matches:
                matching_schools.append({
                    "school_name": meta.get("school_name", "ไม่ระบุ"),
                    "province": meta.get("province", ""),
                    "district": meta.get("district", ""),
                    field_name: count,
                    "school_id": meta.get("school_id", ""),
                })

        logger.info(f"DEBUG: Found {len(matching_schools)} matching schools after filtering")

        reverse_order = operator in ["gt", "gte"]
        matching_schools.sort(key=lambda x: x.get(field_name, 0), reverse=reverse_order)

        limited_schools = matching_schools[:limit]

        op_labels = {
            "lt": "น้อยกว่า", "gt": "มากกว่า",
            "eq": "เท่ากับ", "lte": "ไม่เกิน", "gte": "อย่างน้อย"
        }

        ai_summary = f"พบตามเงื่อนไขทั้งหมด {len(matching_schools)} แห่ง แต่แสดงผลเพียง {len(limited_schools)} แห่ง" + (f" (แสดงครบแล้ว)" if len(matching_schools) == len(limited_schools) else "")

        if len(matching_schools) == 0:
            total_in_area = len(all_schools)
            if total_in_area > 0:
                try:
                    max_school = max(all_schools, key=lambda x: x.payload.get("metadata", {}).get(field_name, 0) or 0)
                    max_val = max_school.payload.get("metadata", {}).get(field_name, 0) or 0
                    max_name = max_school.payload.get("metadata", {}).get("school_name", "ไม่ระบุ")

                    metric_label = "นักเรียน" if field_name == "total_students" else "บุคลากร"

                    ai_summary = f"ไม่พบโรงเรียนที่มี{metric_label} {op_labels.get(operator, operator)} {value} คนในพื้นที่นี้ครับ " \
                                 f"(แต่ในพื้นที่นี้มีโรงเรียนทั้งหมด {total_in_area} แห่ง " \
                                 f"ซึ่งสูงสุดคือ {max_name} มี {max_val} คน)"
                except Exception as e:
                    logger.error(f"Error in smart analysis: {e}")
                    ai_summary = "ไม่พบข้อมูลตามเงื่อนไขครับ"
            else:
                ai_summary = "ไม่พบข้อมูลโรงเรียนในพื้นที่ที่ระบุเลยครับ (อาจสะกดชื่อผิด หรือไม่มีข้อมูลในระบบ)"

                if subdistrict:
                    suggestion = self._get_fuzzy_suggestion(subdistrict, province, district)
                    if suggestion:
                        ai_summary = suggestion

        return {
            "tool": "filter_schools",
            "query": {
                "metric": metric,
                "operator": op_labels.get(operator, operator),
                "value": value,
                "province": province,
                "district": district,
                "subdistrict": subdistrict
            },
            "total_found": len(matching_schools),
            "schools": limited_schools,
            "showing": len(limited_schools),
            "field_name": field_name,
            "ai_summary": ai_summary
        }

    def _get_school_full_details(self, school_name: str, province: str = None, district: str = None, **kwargs) -> Dict[str, Any]:
        """Get full details including GPS, Address, Contact"""
        if not school_name:
            return {"error": "School name is required"}

        ambiguity_check = self._resolve_school_ambiguity(school_name, province, district=district)
        if ambiguity_check['type'] == 'ambiguous':
            logger.info(f"🤔 Ambiguous school name '{school_name}' -> Found {len(ambiguity_check['choices'])} matches")
            return {
                "tool": "get_school_full_details",
                "ambiguous": True,
                "choices": ambiguity_check['choices'],
                "query": {"school_name": school_name}
            }

        results = self._smart_search_school(school_name, province, limit=1)

        if not results and province:
            logger.info(f"⚠️ School '{school_name}' not found in '{province}'. Retrying GLOBAL search...")
            results = self._smart_search_school(school_name, province=None, limit=1)

        if not results:
            suggestions = self._suggest_schools(school_name)
            related_summary = None
            if province:
                try:
                    prov_summary = self._count_schools(province=province)
                    related_summary = {
                        "province": province,
                        "total_schools": prov_summary.get("total_schools", 0),
                        "total_students": prov_summary.get("total_students", 0),
                        "total_teachers": prov_summary.get("total_teachers", 0),
                    }
                except Exception as e:
                    logger.warning(f"⚠️ [GetSchoolDetails] Related summary failed: {e}")
            return {
                "tool": "get_school_full_details",
                "found": False,
                "error": "School not found",
                "suggestions": suggestions,
                "related_summary": related_summary
            }

        point = results[0]
        meta = point.payload.get("metadata", {})

        school_id = meta.get("school_id")
        student_stats = {}
        if school_id:
            try:
                student_stats = self.search_engine.get_student_statistics(school_id)
                logger.info(f"📊 Fetched student stats for {school_id}: {len(student_stats.get('by_grade', {}))} grades found")
            except Exception as e:
                logger.error(f"❌ Failed to fetch student stats: {e}")

        final_result = {
            "tool": "get_school_full_details",
            "found": True,
            "school_name": meta.get("school_name"),
            "school_id": meta.get("school_id"),
            "province": meta.get("province"),
            "district": meta.get("district"),
            "subdistrict": meta.get("subdistrict"),
            "postcode": meta.get("postcode", "-"),
            "agency": meta.get("agency"),
            "phone": meta.get("phone", "-"),
            "website": meta.get("website", "-"),
            "lat": meta.get("lat"),
            "lon": meta.get("lon"),
            "google_maps_url": f"https://www.google.com/maps/search/?api=1&query={meta.get('lat')},{meta.get('lon')}" if meta.get('lat') and meta.get('lon') else None,
            "total_students": meta.get("total_students", 0),
            "total_teachers": meta.get("total_teachers", 0),
            "ratio": meta.get("ratio", 0),
            "student_breakdown": student_stats.get("by_grade", {}),
            "student_breakdown_source": student_stats.get("source"),
            "teacher_breakdown": {},
            "teacher_breakdown_source": None
        }

        if school_id:
            try:
                teacher_stats = self.search_engine.get_teacher_statistics(school_id)
                if teacher_stats:
                    logger.info(f"📊 Fetched teacher stats for {school_id}: {teacher_stats.get('total_teachers')} teachers found")
                    final_result["teacher_breakdown"] = {
                        "by_gender": teacher_stats.get("by_gender"),
                        "by_person_type": teacher_stats.get("by_person_type")
                    }
                    final_result["teacher_breakdown_source"] = teacher_stats.get("source")
            except Exception as e:
                logger.error(f"❌ Failed to fetch teacher stats: {e}")

        return final_result

    def _find_nearby_schools(self, latitude: float, longitude: float,
                             radius_km: float = 5, limit: int = 10) -> Dict[str, Any]:
        """Find schools near GPS coordinates using Haversine distance"""
        import math

        lat = float(latitude)
        lon = float(longitude)
        radius = float(radius_km)

        results = self._scroll_all(self._get_collection("schools"), None, limit=10000)

        def haversine(lat1, lon1, lat2, lon2):
            R = 6371
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
            c = 2 * math.asin(math.sqrt(a))
            return R * c

        nearby = []
        for r in results:
            meta = r.payload.get("metadata", {})
            school_lat = meta.get("lat", meta.get("latitude", 0))
            school_lon = meta.get("lon", meta.get("longitude", 0))

            if not school_lat or not school_lon:
                continue

            try:
                dist = haversine(lat, lon, float(school_lat), float(school_lon))
                if dist <= radius:
                    nearby.append({
                        "school_name": meta.get("school_name"),
                        "province": meta.get("province"),
                        "district": meta.get("district"),
                        "distance_km": round(dist, 2),
                        "lat": school_lat,
                        "lon": school_lon
                    })
            except:
                continue

        nearby.sort(key=lambda x: x["distance_km"])

        return {
            "query": {"latitude": lat, "longitude": lon, "radius_km": radius},
            "schools": nearby[:int(limit)]
        }

    def _get_fuzzy_suggestion(self, subdistrict: str, province: str = None, district: str = None) -> str:
        """Helper to find fuzzy matches for a missing subdistrict"""
        if not subdistrict:
            return ""

        try:
            candidates = set()
            if district or province:
                scope_conditions = []
                if province:
                    scope_conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=self._normalize_province(province))))
                if district:
                    scope_conditions.append(FieldCondition(key="metadata.district", match=MatchText(text=district)))

                scope_filter = self._build_filter(scope_conditions) if scope_conditions else None

                raw_candidates = self._scroll_all(self._get_collection("schools"), scope_filter, limit=200)

                for s in raw_candidates:
                    s_sub = s.payload.get("metadata", {}).get("subdistrict")
                    if s_sub:
                        candidates.add(s_sub)

                if candidates:
                    matches = difflib.get_close_matches(subdistrict, candidates, n=1, cutoff=0.6)
                    if matches:
                        suggested = matches[0]
                        return f"ไม่พบข้อมูลในตำบล '{subdistrict}' ครับ คาดว่าน่าจะเป็น **'{suggested}'** " \
                               f"(ต้องการให้ค้นหาใน '{suggested}' แทนไหมครับ?)"
        except Exception as ex:
            logger.error(f"Fuzzy suggestion helper failed: {ex}")

        return ""
