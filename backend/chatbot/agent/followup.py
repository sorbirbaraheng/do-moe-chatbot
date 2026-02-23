"""
🔄 FollowUpMixin – Context-aware follow-up handling, multi-step plan execution,
                    derived metric computation.
"""

import logging
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

        followup_markers = ["แล้ว", "ล่ะ", "ละ", "ต่อ", "อีก", "เพิ่ม", "ขอ", "รายละเอียด", "เทียบ", "ส่วน", "เฉพาะ"]
        looks_followup = text.startswith(("แล้ว", "งั้น", "ถ้า", "แล้วถ้า")) or any(k in text for k in followup_markers)
        if len(text) > 160 or (len(text) > 40 and not looks_followup):
            return None

        latest_kws = ["ปีล่าสุด", "ล่าสุด", "ปีนี้", "ปัจจุบัน"]
        is_latest = any(k in text for k in latest_kws)

        year = self._extract_year_token(text)
        region = self._extract_region(text)
        province = self._extract_province(text)
        district = self._extract_district(text)
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

        if (
            year is None
            and not is_latest
            and not region
            and not province
            and not district
            and not threshold.get("value")
            and not person_type
            and not has_system_followup
            and not looks_followup
        ):
            return None

        tool = active.get("name") or active.get("tool")
        params = dict(active.get("params", {}) or {})

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

        if tool in ["count_teachers", "count_students"]:
            if year:
                params["year"] = year
            else:
                params.pop("year", None)
            if person_type and tool == "count_teachers":
                params["person_type"] = person_type
            if region and not params.get("region") and not params.get("province"):
                params["region"] = region
            if province and not params.get("province") and not params.get("region"):
                params["province"] = province
            if district and not params.get("district"):
                params["district"] = district
            return [{"name": tool, "params": params}]

        if tool in ["count_schools", "get_ratio"]:
            if region and not params.get("region") and not params.get("province"):
                params["region"] = region
            if province and not params.get("province") and not params.get("region"):
                params["province"] = province
            if district and not params.get("district"):
                params["district"] = district
            return [{"name": tool, "params": params}]

        if tool == "filter_schools":
            if threshold.get("value") is not None:
                params["value"] = threshold["value"]
            if threshold.get("operator"):
                params["operator"] = threshold["operator"]
            if any(k in text for k in ["ครู", "อาจารย์", "บุคลากร"]):
                params["metric"] = "teachers"
            if "นักเรียน" in text:
                params["metric"] = "students"
            if region and not params.get("region") and not params.get("province"):
                params["region"] = region
            if province and not params.get("province") and not params.get("region"):
                params["province"] = province
            if district and not params.get("district"):
                params["district"] = district
            return [{"name": tool, "params": params}]

        if tool == "count_by_system_type":
            if "นอกระบบ" in text:
                params["system_type"] = "นอกระบบ"
            if "ในระบบ" in text:
                params["system_type"] = "ในระบบ"
            if region and not params.get("region") and not params.get("province"):
                params["region"] = region
            if province and not params.get("province") and not params.get("region"):
                params["province"] = province
            if district and not params.get("district"):
                params["district"] = district
            return [{"name": tool, "params": params}]

        if tool == "ranking":
            if any(k in text for k in ["น้อยที่สุด", "ต่ำสุด", "ต่ำที่สุด", "น้อยสุด"]):
                params["order"] = "least"
            elif any(k in text for k in ["มากที่สุด", "สูงสุด", "เยอะที่สุด", "มากสุด"]):
                params["order"] = "most"
            if person_type and params.get("metric") == "teachers":
                params["person_type"] = person_type
            if region and not params.get("region") and not params.get("province"):
                params["region"] = region
            if province and not params.get("province") and not params.get("region"):
                params["province"] = province
            if district and not params.get("district") and params.get("scope") in ["subdistrict"]:
                params["district"] = district
            return [{"name": tool, "params": params}]

        if tool == "get_school_full_details":
            school_name = params.get("school_name")
            if not school_name:
                return None

            follow_params = {"school_name": school_name}
            if params.get("province"):
                follow_params["province"] = params.get("province")
            if year:
                follow_params["year"] = year

            if any(k in text for k in ["ครู", "อาจารย์", "บุคลากร"]):
                if person_type:
                    follow_params["person_type"] = person_type
                return [{"name": "count_teachers", "params": follow_params}]
            if any(k in text for k in ["นักเรียน", "ชั้น", "ม.", "ป.", "อนุบาล"]):
                grade = self._extract_grade(text)
                if grade:
                    follow_params["grade"] = grade
                return [{"name": "count_students", "params": follow_params}]
            if any(k in text for k in ["รายละเอียด", "อยู่ที่ไหน", "พิกัด", "แผนที่"]):
                return [{"name": "get_school_full_details", "params": follow_params}]

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
