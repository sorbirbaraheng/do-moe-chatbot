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

        strong_followup_markers = ["แล้ว", "ล่ะ", "ละ", "ต่อ", "อีก", "เพิ่ม", "งั้น", "ถ้า", "แล้วถ้า"]
        weak_followup_markers = ["ขอรายละเอียด", "รายละเอียดเพิ่ม", "พิกัด", "อยู่ที่ไหน", "เบอร์ติดต่อ"]
        starts_followup = text.startswith(tuple(strong_followup_markers))
        year_only_followup = bool(
            re.match(r'^\s*(?:แล้ว\s*)?ปี(?:การศึกษา)?\s*\d{2,4}(?:\s*(?:ละ|ล่ะ|ล่ะครับ|ละครับ|หล่ะ))?\s*$', text)
        )
        looks_followup = starts_followup or any(k in text for k in strong_followup_markers + weak_followup_markers) or year_only_followup
        if len(text) > 160 or (len(text) > 50 and not looks_followup):
            return None

        asks_teachers = any(k in text for k in ["ครู", "อาจารย์", "บุคลากร"])
        asks_students = any(k in text for k in ["นักเรียน", "ผู้เรียน", "เด็ก", "ชั้น", "ม.", "ป.", "อนุบาล"])
        asks_schools = any(k in text for k in ["โรงเรียน", "สถานศึกษา", "กี่โรง", "กี่แห่ง"])

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

        # Don't hijack standalone explicit-scope queries into follow-up flow
        if has_explicit_scope and not starts_followup and not year_only_followup and len(text) > 16:
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

        tool = active.get("name") or active.get("tool")
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
                "count_by_system_type": {"province", "district", "system_type", "year"},
                "list_schools": {"province", "district", "region", "agency", "limit", "year"},
                "search_schools": {"school_name", "province", "district", "region", "agency", "limit", "year"},
                "ranking": {"metric", "order", "scope", "province", "region", "district", "limit", "year", "person_type"},
                "filter_schools": {"metric", "operator", "value", "province", "region", "district", "subdistrict", "limit", "year"},
                "get_school_full_details": {"school_name", "province", "year"},
                "get_province_summary": {"province", "year"},
                "get_ratio": {"school_name", "province", "year"},
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
            if asks_teachers or asks_students or asks_schools or agency:
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
            if any(k in text for k in ["น้อยที่สุด", "ต่ำสุด", "ต่ำที่สุด", "น้อยสุด"]):
                params["order"] = "least"
            elif any(k in text for k in ["มากที่สุด", "สูงสุด", "เยอะที่สุด", "มากสุด"]):
                params["order"] = "most"
            if asks_teachers:
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
            return [{"name": "ranking", "params": _prune_params_for_tool("ranking", params)}]

        if tool == "get_school_full_details":
            school_name = params.get("school_name")
            if not school_name:
                return None

            follow_params = {"school_name": school_name}
            if params.get("province"):
                follow_params["province"] = params.get("province")
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
