"""
🔄 FollowUpMixin – Context-aware follow-up handling, multi-step plan execution,
                    derived metric computation.
"""

import logging
import re
from typing import Dict, Any, List, Optional

from ..tools import get_tool_by_name

logger = logging.getLogger(__name__)


class FollowUpMixin:
    """Follow-up query handling, multi-step plan execution, and derived metrics."""

    def _try_followup_from_active_query(self, question: str, context: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        active = context.get("last_active_query")
        if not active or not isinstance(active, dict):
            return None

        text = (question or "").strip()
        if not text:
            return None

        strong_followup_markers = ["แล้ว", "ล่ะ", "ละ", "ต่อ", "อีก", "เพิ่ม", "งั้น", "ถ้า", "แล้วถ้า", "ขอแบบ", "แยกสังกัด", "แยกตามสังกัด"]
        weak_followup_markers = ["ขอรายละเอียด", "รายละเอียดเพิ่ม", "พิกัด", "อยู่ที่ไหน", "เบอร์ติดต่อ"]
        context_followup_markers = [
            "เทียบ", "เปรียบเทียบ", "เปลี่ยนแปลง", "ต่างกัน",
            "แยกตามภูมิภาค", "แยกภาค", "ภาคไหน", "แต่ละภาค", "ทั้ง 6 ภาค", "6 ภาค"
        ]
        starts_followup = text.startswith(tuple(strong_followup_markers))
        year_only_followup = bool(
            re.match(r'^\s*(?:แล้ว\s*)?ปี(?:การศึกษา)?\s*\d{2,4}(?:\s*(?:ละ|ล่ะ|ล่ะครับ|ละครับ|หล่ะ))?\s*$', text)
        )
        looks_followup = (
            starts_followup
            or any(k in text for k in strong_followup_markers + weak_followup_markers + context_followup_markers)
            or year_only_followup
        )
        if len(text) > 160 or (len(text) > 50 and not looks_followup):
            return None

        asks_teachers = any(k in text for k in ["ครู", "อาจารย์", "บุคลากร"])
        asks_students = any(k in text for k in ["นักเรียน", "ผู้เรียน", "เด็ก", "ชั้น", "ม.", "ป.", "อนุบาล"])
        asks_schools = any(k in text for k in ["โรงเรียน", "สถานศึกษา", "กี่โรง", "กี่แห่ง", "แยกสังกัด", "แยกตามสังกัด", "ตามสังกัด"])

        latest_kws = ["ปีล่าสุด", "ล่าสุด", "ปีนี้", "ปัจจุบัน"]
        is_latest = any(k in text for k in latest_kws)

        year = self._extract_year_token(text)
        region = self._extract_region(text)
        province = self._extract_province(text)
        district = self._extract_district(text)
        grade = self._extract_grade(text)
        agency = self._extract_agency(text)
        has_explicit_scope = bool(region or province or district)

        has_system_followup = any(k in text for k in ["ในระบบ", "นอกระบบ"])
        if not region and "ทั้งภาค" in text:
            region = self._extract_region(text.replace("ทั้ง", ""))
        threshold = self._extract_threshold_followup(text)

        person_type = self._extract_person_type(text)
        if isinstance(person_type, str):
            person_type = {
                "ครูอัตราจ้าง": "ลูกจ้างชั่วคราว",
                "อัตราจ้าง": "ลูกจ้างชั่วคราว",
                "ครูจ้าง": "ลูกจ้างชั่วคราว",
                "ข้าราชการ": "ข้าราชการครู",
            }.get(person_type, person_type)

        active_tool = active.get("name") or active.get("tool")
        summary_scope_followup = (
            active_tool in ["get_national_summary", "get_province_summary", "compare_years", "ranking"]
            and any(k in text for k in ["แยกตามภูมิภาค", "แยกภาค", "ภาคไหน", "6 ภาค", "ทั้ง 6 ภาค", "แต่ละภาค", "อัตราส่วน", "ต่อครู"])
        )
        # Don't hijack standalone explicit-scope queries into follow-up flow,
        # except summary/compare continuity queries that intentionally pivot scope.
        if has_explicit_scope and not starts_followup and not year_only_followup and len(text) > 16 and not summary_scope_followup:
            return None

        if (
            year is None
            and not is_latest
            and not region
            and not province
            and not district
            and not grade
            and not agency
            and not threshold.get("value")
            and not person_type
            and not has_system_followup
            and not looks_followup
        ):
            return None

        tool = active_tool
        params = dict(active.get("params", {}) or {})

        def _apply_scope_overrides(base: Dict[str, Any]) -> Dict[str, Any]:
            out = dict(base or {})
            if province:
                out["province"] = province
                out.pop("region", None)
            elif region:
                out["region"] = region
                out.pop("province", None)
            if district:
                out["district"] = district
            return out

        def _apply_year_overrides(base: Dict[str, Any]) -> Dict[str, Any]:
            out = dict(base or {})
            if year:
                out["year"] = year
            elif is_latest:
                out.pop("year", None)
            return out

        def _prune_params_for_tool(tool_name: str, raw: Dict[str, Any]) -> Dict[str, Any]:
            allow = {
                "count_students": {"school_name", "province", "district", "region", "grade", "gender", "year", "agency"},
                "count_teachers": {"school_name", "province", "district", "region", "gender", "person_type", "year"},
                "count_schools": {"province", "district", "subdistrict", "agency", "region", "year"},
                "count_by_system_type": {"province", "district", "region", "system_type", "year"},
                "analyze_gender_ratio": {"province", "district", "region", "school_name", "year"},
                "list_schools": {"province", "district", "region", "agency", "limit", "year"},
                "search_schools": {"school_name", "province", "district", "region", "agency", "limit", "year"},
                "ranking": {"metric", "order", "scope", "province", "region", "district", "limit", "year", "person_type"},
                "filter_schools": {"metric", "operator", "value", "province", "region", "district", "subdistrict", "limit", "year"},
                "get_school_full_details": {"school_name", "province", "year"},
                "get_province_summary": {"province", "year"},
                "get_national_summary": {"year"},
                "get_ratio": {"school_name", "province", "year"},
                "compare_years": {"year1", "year2", "province", "region", "school_name", "metric"},
                "find_best_ratio_schools": {"province", "order", "limit"},
                "get_district_summary": {"province", "district", "year"},
                "ranking_subdistricts": {"province", "district", "metric", "order", "limit"},
            }
            keys = allow.get(tool_name)
            if not keys:
                return dict(raw or {})
            return {k: v for k, v in (raw or {}).items() if k in keys and v is not None}

        # Multi-step plan follow-up
        if tool == "__multi_step__":
            plan = params.get("plan") or {}
            steps = plan.get("steps") or []
            if region or province:
                for step in steps:
                    p = step.get("params") or {}
                    if region and not p.get("region") and not p.get("province"):
                        p["region"] = region
                    if province and not p.get("province") and not p.get("region"):
                        p["province"] = province
                    step["params"] = p
                plan["steps"] = steps
            return [{"name": "__multi_step__", "params": {"plan": plan}}]

        if tool in ["count_students", "count_teachers"]:
            # ── Year comparison follow-up ────────────────────────
            is_year_compare = any(k in text for k in [
                "เทียบ", "เปรียบเทียบ", "เปลี่ยนแปลง", "ต่างกัน",
                "เปอร์เซ็นต์", "เพิ่มขึ้น", "ลดลง", "กี่%", "คิดเป็น%"
            ])
            if is_year_compare and year:
                from ..core.constants import V5_YEAR
                active_year = params.get("year", V5_YEAR)
                compare_params = {
                    "year1": str(year),
                    "year2": str(active_year) if str(active_year) != str(year) else V5_YEAR,
                    "metric": "all",
                }
                if params.get("province"):
                    compare_params["province"] = params["province"]
                if params.get("region"):
                    compare_params["region"] = params["region"]
                return [{"name": "compare_years", "params": _prune_params_for_tool("compare_years", compare_params)}]

            # ── Region breakdown follow-up → national summary ───
            asks_region_fu = any(k in text for k in [
                "แยกตามภูมิภาค", "แยกภาค", "ภาคไหน", "6 ภาค",
                "ทั้ง 6 ภาค", "แต่ละภาค"
            ])
            if asks_region_fu and not params.get("province"):
                return [{"name": "get_national_summary", "params": _prune_params_for_tool("get_national_summary", {})}]

            if has_system_followup:
                system_params = {
                    k: v for k, v in params.items()
                    if k in ["province", "district", "region", "year"]
                }
                system_params = _apply_scope_overrides(system_params)
                system_params = _apply_year_overrides(system_params)
                system_params["system_type"] = "นอกระบบ" if "นอกระบบ" in text else "ในระบบ"
                return [{"name": "count_by_system_type", "params": _prune_params_for_tool("count_by_system_type", system_params)}]

            target_tool = tool
            if asks_teachers:
                target_tool = "count_teachers"
            elif asks_students:
                target_tool = "count_students"
            elif asks_schools or agency:
                target_tool = "count_schools"

            params = _apply_scope_overrides(params)
            params = _apply_year_overrides(params)
            if target_tool == "count_students":
                params.pop("person_type", None)
                if grade:
                    params["grade"] = grade
            elif target_tool == "count_teachers":
                params.pop("grade", None)
                if person_type:
                    params["person_type"] = person_type
            else:
                params.pop("grade", None)
                params.pop("person_type", None)
                if agency:
                    params["agency"] = agency
            return [{"name": target_tool, "params": _prune_params_for_tool(target_tool, params)}]

        if tool in ["count_schools", "get_ratio"]:
            # ── Year comparison follow-up ────────────────────────
            is_year_compare = any(k in text for k in [
                "เทียบ", "เปรียบเทียบ", "เปลี่ยนแปลง", "ต่างกัน",
                "เปอร์เซ็นต์", "เพิ่มขึ้น", "ลดลง", "กี่%", "คิดเป็น%"
            ])
            if is_year_compare and year:
                from ..core.constants import V5_YEAR
                active_year = params.get("year", V5_YEAR)
                compare_params = {
                    "year1": str(year),
                    "year2": str(active_year) if str(active_year) != str(year) else V5_YEAR,
                    "metric": "all",
                }
                if params.get("province"):
                    compare_params["province"] = params["province"]
                return [{"name": "compare_years", "params": _prune_params_for_tool("compare_years", compare_params)}]

            # ── Region breakdown follow-up → national summary ───
            asks_region_fu = any(k in text for k in [
                "แยกตามภูมิภาค", "แยกภาค", "ภาคไหน", "6 ภาค",
                "ทั้ง 6 ภาค", "แต่ละภาค"
            ])
            if asks_region_fu and not params.get("province"):
                return [{"name": "get_national_summary", "params": _prune_params_for_tool("get_national_summary", {})}]

            if asks_teachers or asks_students:
                converted_tool = "count_teachers" if asks_teachers else "count_students"
                converted_params = {
                    k: v for k, v in params.items()
                    if k in ["school_name", "province", "district", "region", "year"]
                }
                converted_params = _apply_scope_overrides(converted_params)
                converted_params = _apply_year_overrides(converted_params)
                if converted_tool == "count_students" and grade:
                    converted_params["grade"] = grade
                if converted_tool == "count_teachers" and person_type:
                    converted_params["person_type"] = person_type
                return [{"name": converted_tool, "params": _prune_params_for_tool(converted_tool, converted_params)}]

            params = _apply_scope_overrides(params)
            params = _apply_year_overrides(params)
            if tool == "count_schools" and agency:
                params["agency"] = agency
            return [{"name": tool, "params": _prune_params_for_tool(tool, params)}]

        if tool == "get_province_summary":
            asks_ratio_local = any(
                k in text for k in ["อัตราส่วน", "สัดส่วน", "ต่อครู", "ครูต่อนักเรียน", "นักเรียนต่อครู", "ratio"]
            )
            # Prioritize ratio intent over generic teacher intent
            # (e.g. "สัดส่วนครูต่อนักเรียน" should map to ratio, not count_teachers)
            if (asks_teachers or asks_students or asks_schools or agency) and not any(
                k in text for k in ["อัตราส่วน", "สัดส่วน", "ต่อครู", "ครูต่อนักเรียน", "นักเรียนต่อครู", "ratio"]
            ):
                converted_tool = "count_teachers" if asks_teachers else ("count_students" if asks_students else "count_schools")
                converted_params = {
                    k: v for k, v in params.items()
                    if k in ["province", "district", "region", "year", "agency"]
                }
                converted_params = _apply_scope_overrides(converted_params)
                converted_params = _apply_year_overrides(converted_params)
                if converted_tool == "count_students" and grade:
                    converted_params["grade"] = grade
                if converted_tool == "count_teachers" and person_type:
                    converted_params["person_type"] = person_type
                if converted_tool == "count_schools" and agency:
                    converted_params["agency"] = agency
                return [{"name": converted_tool, "params": _prune_params_for_tool(converted_tool, converted_params)}]

            if asks_ratio_local:
                ratio_params = {}
                if params.get("province"):
                    ratio_params["province"] = params["province"]
                if params.get("year"):
                    ratio_params["year"] = params["year"]
                return [{"name": "get_ratio", "params": _prune_params_for_tool("get_ratio", ratio_params)}]

            params = _apply_scope_overrides(params)
            params = _apply_year_overrides(params)
            return [{"name": "get_province_summary", "params": _prune_params_for_tool("get_province_summary", params)}]

        if tool in ["list_schools", "search_schools"]:
            params = _apply_scope_overrides(params)
            params = _apply_year_overrides(params)
            if agency:
                params["agency"] = agency
            if not params.get("limit"):
                params["limit"] = 10
            return [{"name": tool, "params": _prune_params_for_tool(tool, params)}]

        if tool == "filter_schools":
            params = _apply_scope_overrides(params)
            params = _apply_year_overrides(params)
            if threshold.get("value") is not None:
                params["value"] = threshold["value"]
            if threshold.get("operator"):
                params["operator"] = threshold["operator"]
            if asks_teachers:
                params["metric"] = "teachers"
            elif asks_students:
                params["metric"] = "students"
            return [{"name": "filter_schools", "params": _prune_params_for_tool("filter_schools", params)}]

        if tool == "count_by_system_type":
            params = _apply_scope_overrides(params)
            params = _apply_year_overrides(params)
            if "นอกระบบ" in text:
                params["system_type"] = "นอกระบบ"
            if "ในระบบ" in text:
                params["system_type"] = "ในระบบ"
            return [{"name": "count_by_system_type", "params": _prune_params_for_tool("count_by_system_type", params)}]

        if tool == "ranking":
            params = _apply_scope_overrides(params)
            params = _apply_year_overrides(params)
            limit_match = re.search(r'(?:top\s*(\d+))|(?:เอา\s*(\d+))|(\d+)\s*อันดับ', text.lower())
            if limit_match:
                try:
                    params["limit"] = int(limit_match.group(1) or limit_match.group(2) or limit_match.group(3))
                except Exception:
                    pass

            ratio_kws = ["อัตราส่วน", "ครูต่อ", "ครูต่อนักเรียน", "นักเรียนต่อครู", "ต่อครู", "ratio", "ไม่ทั่วถึง", "ขาดแคลนครู"]
            asks_ratio = any(k in text for k in ratio_kws)
            asks_district = any(k in text for k in ["อำเภอไหน", "อำเภอ", "district"])
            asks_school_entity = any(k in text for k in ["โรงเรียนไหน", "โรงเรียนที่", "กี่โรง"])
            asks_year_compare = any(k in text for k in [
                "เทียบ", "เปรียบเทียบ", "เปลี่ยนแปลง", "ต่างกัน",
                "เปอร์เซ็นต์", "เพิ่มขึ้น", "ลดลง", "กี่%", "คิดเป็น%"
            ])
            asks_region_entity = (
                any(k in text for k in ["ภาคไหน", "ภาคใด", "ภูมิภาคไหน", "ภูมิภาคใด"])
                or ("ระดับภาค" in text and not any(k in text for k in ["จังหวัด", "อำเภอ", "ตำบล", "โรงเรียน"]))
                or any(k in text for k in ["แยกตามภูมิภาค", "แยกภาค", "ทั้ง 6 ภาค", "6 ภาค", "แต่ละภาค"])
            )

            # ── Resolve province from context for drill-down ──────
            # Ranking at province scope won't have 'province' in params;
            # we must pull it from the last_active_query result or memory.
            ctx_province = params.get("province") or context.get("last_province")

            # ── (1) Year compare from ranking context ──────────────
            if asks_year_compare and (year or any(k in text for k in ["เทียบ", "เปรียบ"])):
                from ..core.constants import V5_YEAR
                compare_params = {
                    "metric": "all",
                }
                if year:
                    active_year = params.get("year", V5_YEAR)
                    compare_params["year1"] = str(year)
                    compare_params["year2"] = str(active_year) if str(active_year) != str(year) else V5_YEAR
                else:
                    compare_params["year1"] = "2566"
                    compare_params["year2"] = str(params.get("year", V5_YEAR))
                if ctx_province:
                    compare_params["province"] = ctx_province
                return [{"name": "compare_years", "params": _prune_params_for_tool("compare_years", compare_params)}]

            # ── (2) District drill-down from province ranking ──────
            if asks_district and ctx_province:
                district_params = dict(params)
                district_params["scope"] = "district"
                district_params["province"] = ctx_province
                if not district_params.get("limit"):
                    district_params["limit"] = 5
                if asks_ratio:
                    district_params["metric"] = "ratio"
                elif asks_teachers:
                    district_params["metric"] = "teachers"
                elif asks_students:
                    district_params["metric"] = "students"
                elif asks_schools:
                    district_params["metric"] = "schools"
                return [{"name": "ranking", "params": _prune_params_for_tool("ranking", district_params)}]

            # ── (3) School drill-down from ratio ranking ───────────
            is_ratio_context = params.get("metric") == "ratio" or asks_ratio
            if asks_school_entity and is_ratio_context and ctx_province:
                school_order = "worst"
                if any(k in text for k in ["ดีที่สุด", "ดีสุด", "ต่ำสุด", "น้อยสุด", "best"]):
                    school_order = "best"
                school_limit = params.get("limit", 5)
                return [{"name": "find_best_ratio_schools", "params": _prune_params_for_tool(
                    "find_best_ratio_schools",
                    {"province": ctx_province, "order": school_order, "limit": school_limit}
                )}]

            # ── (4) Standalone reverse order ("ต่ำสุดล่ะ") ─────────
            asks_reverse_low = any(k in text for k in ["ต่ำสุด", "น้อยที่สุด", "ต่ำที่สุด", "น้อยสุด"])
            asks_reverse_high = any(k in text for k in ["มากที่สุด", "สูงสุด", "เยอะที่สุด", "มากสุด"])
            if asks_reverse_low or asks_reverse_high:
                # For ratio metric, "ต่ำสุด" means best ratio (fewer students per teacher)
                if params.get("metric") == "ratio":
                    if asks_reverse_low:
                        # If previous was worst, flip to best; if was best, keep
                        new_order = "best" if params.get("order") in ["worst", "most"] else "worst"
                    else:
                        new_order = "worst" if params.get("order") in ["best", "least"] else "most"
                    # Route to find_best_ratio_schools if province-scoped
                    if ctx_province and params.get("scope") in ["province", "provinces", None]:
                        return [{"name": "find_best_ratio_schools", "params": _prune_params_for_tool(
                            "find_best_ratio_schools",
                            {"province": ctx_province, "order": new_order, "limit": params.get("limit", 5)}
                        )}]
                    params["order"] = new_order
                else:
                    params["order"] = "least" if asks_reverse_low else "most"
            elif any(k in text for k in ["น้อยที่สุด", "ต่ำสุด", "ต่ำที่สุด", "น้อยสุด"]):
                params["order"] = "least"
            elif any(k in text for k in ["มากที่สุด", "สูงสุด", "เยอะที่สุด", "มากสุด"]):
                params["order"] = "most"

            if asks_ratio:
                params["metric"] = "ratio"
            elif asks_teachers:
                params["metric"] = "teachers"
            elif asks_students:
                params["metric"] = "students"
            elif asks_schools:
                params["metric"] = "schools"
            if params.get("metric") == "teachers" and person_type:
                params["person_type"] = person_type
            if params.get("metric") == "schools" and agency:
                params["agency"] = agency
            if district and not params.get("district") and params.get("scope") == "subdistrict":
                params["district"] = district
            if asks_region_entity:
                params["scope"] = "region"
                # Region ranking should compare all regions, not be constrained by stale scope
                params.pop("province", None)
                params.pop("district", None)
                params.pop("region", None)
            return [{"name": "ranking", "params": _prune_params_for_tool("ranking", params)}]

        if tool == "get_school_full_details":
            school_name = params.get("school_name")
            if not school_name:
                return None

            follow_params = {"school_name": school_name}
            if params.get("province"):
                follow_params["province"] = params.get("province")
            if params.get("year"):
                follow_params["year"] = params.get("year")
            follow_params = _apply_year_overrides(follow_params)

            if asks_teachers:
                if person_type:
                    follow_params["person_type"] = person_type
                return [{"name": "count_teachers", "params": _prune_params_for_tool("count_teachers", follow_params)}]
            if asks_students:
                if grade:
                    follow_params["grade"] = grade
                return [{"name": "count_students", "params": _prune_params_for_tool("count_students", follow_params)}]
            if any(k in text for k in ["รายละเอียด", "อยู่ที่ไหน", "พิกัด", "แผนที่"]):
                return [{"name": "get_school_full_details", "params": _prune_params_for_tool("get_school_full_details", follow_params)}]

        if tool == "compare_years":
            is_year_compare = any(k in text for k in ["เทียบ", "เปรียบเทียบ", "ต่างกัน", "เปลี่ยนแปลง", "เปอร์เซ็นต์", "เพิ่มขึ้น", "ลดลง", "กี่%", "คิดเป็น%"])
            asks_ratio = any(k in text for k in ["อัตราส่วน", "สัดส่วน", "ต่อครู", "ครูต่อนักเรียน", "นักเรียนต่อครู", "ratio"])
            asks_region = any(k in text for k in ["แยกตามภาค", "แยกภาค", "ภาคไหน", "6 ภาค", "ทั้ง 6 ภาค", "แต่ละภาค", "ระดับภาค"])

            # Prefer the newer year from compare context when pivoting to single-year tools
            latest_year = None
            for cand in [params.get("year2"), params.get("year1")]:
                try:
                    latest_year = int(cand)
                    break
                except Exception:
                    continue

            if is_year_compare and year:
                compare_params = {
                    "year1": str(year),
                    "year2": str(params.get("year2") or params.get("year1") or year),
                    "metric": "all",
                }
                if params.get("province"):
                    compare_params["province"] = params["province"]
                elif params.get("region"):
                    compare_params["region"] = params["region"]
                if params.get("school_name"):
                    compare_params["school_name"] = params["school_name"]
                return [{"name": "compare_years", "params": _prune_params_for_tool("compare_years", compare_params)}]

            if asks_ratio and asks_region:
                rank_params = {"metric": "ratio", "order": "most", "scope": "region", "limit": 6}
                if latest_year:
                    rank_params["year"] = latest_year
                return [{"name": "ranking", "params": _prune_params_for_tool("ranking", rank_params)}]

            if asks_region:
                metric = "students"
                if asks_teachers:
                    metric = "teachers"
                elif asks_schools:
                    metric = "schools"
                rank_params = {"metric": metric, "order": "most", "scope": "region", "limit": 6}
                if latest_year:
                    rank_params["year"] = latest_year
                return [{"name": "ranking", "params": _prune_params_for_tool("ranking", rank_params)}]

            if asks_teachers or asks_students or asks_schools:
                base = {}
                if params.get("province"):
                    base["province"] = params["province"]
                elif params.get("region"):
                    base["region"] = params["region"]
                if latest_year:
                    base["year"] = latest_year
                if asks_teachers:
                    if person_type:
                        base["person_type"] = person_type
                    return [{"name": "count_teachers", "params": _prune_params_for_tool("count_teachers", base)}]
                if asks_students:
                    if grade:
                        base["grade"] = grade
                    return [{"name": "count_students", "params": _prune_params_for_tool("count_students", base)}]
                if asks_schools:
                    if agency:
                        base["agency"] = agency
                    return [{"name": "count_schools", "params": _prune_params_for_tool("count_schools", base)}]

        # ── Follow-up from summary tools (national / province) ──────
        if tool in ["get_national_summary", "get_province_summary"]:
            is_year_compare = any(k in text for k in ["เทียบ", "เปรียบเทียบ", "ต่างกัน", "เปลี่ยนแปลง", "เปอร์เซ็นต์", "เพิ่มขึ้น", "ลดลง", "กี่%", "คิดเป็น%"])
            asks_ratio = any(k in text for k in ["อัตราส่วน", "สัดส่วน", "ต่อครู", "ครูต่อนักเรียน", "ratio"])
            asks_region = any(k in text for k in ["แยกตามภาค", "แยกภาค", "ภาคไหน", "6 ภาค", "แต่ละภาค"])
            asks_agency = any(k in text for k in ["แยกสังกัด", "แยกตามสังกัด", "สังกัดไหน"])

            if is_year_compare and year:
                # Determine the other year from context or default latest
                from ..core.constants import V5_YEAR, AVAILABLE_YEARS
                # Prefer year from the original active query (e.g., user asked national summary for 2568)
                active_year = (params.get("year") or V5_YEAR)
                other_year = str(active_year) if str(active_year) != str(year) else V5_YEAR
                compare_params = {"year1": str(year), "year2": other_year, "metric": "all"}
                if tool == "get_province_summary" and params.get("province"):
                    compare_params["province"] = params["province"]
                return [{"name": "compare_years", "params": _prune_params_for_tool("compare_years", compare_params)}]

            if asks_ratio and asks_region:
                return [{"name": "ranking", "params": {"metric": "ratio", "order": "most", "scope": "region", "limit": 6}}]

            if asks_region:
                metric = "students"
                if asks_teachers:
                    metric = "teachers"
                elif asks_schools:
                    metric = "schools"
                return [{"name": "ranking", "params": {"metric": metric, "order": "most", "scope": "region", "limit": 6}}]

            if asks_agency:
                rank_params = {"metric": "schools", "order": "most", "limit": 10}
                if tool == "get_province_summary" and params.get("province"):
                    rank_params["province"] = params["province"]
                return [{"name": "ranking_by_agency", "params": rank_params}]

            if asks_ratio:
                ratio_params = {}
                if tool == "get_province_summary" and params.get("province"):
                    ratio_params["province"] = params["province"]
                if params.get("year"):
                    ratio_params["year"] = params["year"]
                return [{"name": "get_ratio", "params": _prune_params_for_tool("get_ratio", ratio_params)}]

            if asks_teachers:
                t_params = {}
                if tool == "get_province_summary" and params.get("province"):
                    t_params["province"] = params["province"]
                if person_type:
                    t_params["person_type"] = person_type
                return [{"name": "count_teachers", "params": _prune_params_for_tool("count_teachers", t_params)}]

            if asks_students:
                s_params = {}
                if tool == "get_province_summary" and params.get("province"):
                    s_params["province"] = params["province"]
                if grade:
                    s_params["grade"] = grade
                return [{"name": "count_students", "params": _prune_params_for_tool("count_students", s_params)}]

            if asks_schools or agency:
                sc_params = {}
                if tool == "get_province_summary" and params.get("province"):
                    sc_params["province"] = params["province"]
                if agency:
                    sc_params["agency"] = agency
                return [{"name": "count_schools", "params": _prune_params_for_tool("count_schools", sc_params)}]

        return None

    def _run_multi_step_plan(self, question: str, plan: Dict[str, Any]) -> str:
        steps = plan.get("steps") or []
        derive = plan.get("derive") or {}

        if not steps:
            return self._format_ask_back("ขอรายละเอียดเพิ่มอีกนิดได้ไหมครับ เพื่อคำนวณให้ถูกต้อง")

        results_by_alias = {}
        for step in steps:
            tool = step.get("tool")
            params = step.get("params") or {}
            save_as = step.get("save_as") or tool

            if not tool or (tool != "general_chat" and not get_tool_by_name(tool)):
                return self._format_ask_back("ขอรายละเอียดเพิ่มอีกนิดได้ไหมครับ เพื่อเลือกเครื่องมือให้ถูกต้อง")

            results_by_alias[save_as] = self.tool_executor.execute(tool, params)

        derived = self._compute_derived(results_by_alias, derive)
        if not derived:
            return self._format_ask_back("ขอรายละเอียดเพิ่มอีกนิดได้ไหมครับ เพื่อคำนวณให้ถูกต้อง")

        return self._generate_response(question, [derived])

    def _compute_derived(self, results_by_alias: Dict[str, Dict[str, Any]], derive: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        operation = (derive.get("operation") or "").strip().lower()
        numerator_ref = derive.get("numerator") or {}
        denominator_ref = derive.get("denominator") or {}
        precision = derive.get("precision", 2)
        label = derive.get("label") or "ผลลัพธ์ที่คำนวณได้"
        unit = derive.get("unit") or ""

        num_val = self._extract_value(results_by_alias, numerator_ref)
        den_val = self._extract_value(results_by_alias, denominator_ref)

        if num_val is None or den_val in (None, 0):
            return None

        try:
            value = float(num_val) / float(den_val)
        except Exception:
            return None

        try:
            precision = int(precision)
        except Exception:
            precision = 2
        value = round(value, max(0, min(6, precision)))

        return {
            "tool": "derived_metric",
            "label": label,
            "value": value,
            "unit": unit,
            "operation": operation,
            "components": {
                "numerator": num_val,
                "denominator": den_val
            },
            "sources": results_by_alias
        }

    def _extract_value(self, results_by_alias: Dict[str, Dict[str, Any]], ref: Dict[str, Any]) -> Optional[float]:
        step = ref.get("step")
        field = ref.get("field")
        if not step or step not in results_by_alias:
            return None
        res = results_by_alias.get(step) or {}
        if field and field in res:
            return res.get(field)
        tool = res.get("tool")
        if tool == "count_teachers":
            return res.get("total_teachers")
        if tool == "count_students":
            return res.get("total_students")
        if tool == "count_schools":
            return res.get("total_schools")
        return None
