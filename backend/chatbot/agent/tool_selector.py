"""ToolSelectorMixin"""
import json
import logging
import re
from typing import Dict, Any, List, Optional
from ..tools import get_tool_by_name, TOOL_SELECTION_PROMPT
from ..core.constants import THAI_PROVINCES, PROVINCE_ALIASES, REGIONS
from ..search.entity_extractor import (extract_person_type_smart, extract_grade_smart, extract_area_smart, extract_district_smart, fetch_valid_values, extract_entities_via_llm, extract_query_structured_via_llm)
logger = logging.getLogger(__name__)

class ToolSelectorMixin:

    def _select_tools(self, question: str, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Structured-only tool selection:
        - Use LLM to return a structured tool + params
        - Validate + ask-back when unclear
        - No keyword inference or heuristic enrichment
        """
        logger.info("🧠 Structured Tool Selection: extracting query JSON...")

        # 0) Follow-up on previous pending query (e.g., user answers "ปีล่าสุดครับ")
        followup = self._try_followup_from_active_query(question, context or {})
        if followup:
            return followup

        # Quick path for greetings/thanks (avoid unnecessary ask-back/LLM)
        q = (question or "").strip().lower()
        if q:
            greet_keywords = ["สวัสดี", "หวัดดี", "hello", "hi", "ดีครับ", "ขอบคุณ", "ขอบใจ", "โอเค", "ok"]
            if len(q) <= 20 and any(k in q for k in greet_keywords):
                msg = "สวัสดีครับ ยินดีช่วยครับ อยากสอบถามเรื่องการศึกษาด้านไหนครับ"
                return [{"name": "__ask_back__", "params": {"message": msg, "pending_tool": None}}]

        # Quick ask-back: subjective "best school" needs explicit metric/scope
        q_raw = (question or "").strip()
        q_norm = q_raw.replace(" ", "")
        if q_raw:
            has_best_school_phrase = any(k in q_norm for k in ["โรงเรียนไหนดี", "ไหนดีสุด", "ดีที่สุด"])
            has_school_context = "โรงเรียน" in q_raw
            has_metric_hint = any(k in q_raw for k in ["อัตราส่วน", "นักเรียน", "ครู", "ผลสอบ", "คะแนน", "ใกล้", "สังกัด", "ค่าเทอม"])
            if has_best_school_phrase and has_school_context and not has_metric_hint:
                msg = "ต้องการดูคำว่า 'ดีที่สุด' ในแง่ไหนครับ เช่น อัตราส่วนครูต่อนักเรียน หรือจำนวนนักเรียน"
                return [{"name": "__ask_back__", "params": {"message": msg, "pending_tool": None}}]

        # Quick-path: threshold follow-up ("มากกว่า 800 คนล่ะ")
        # Avoid dropping to GENERAL/ask-back when user omits metric but previous scope exists.
        q_followup_markers = ["แล้ว", "ล่ะ", "ละ", "ต่อ", "อีก", "เพิ่ม", "งั้น", "ถ้า", "แล้วถ้า"]
        threshold_info = self._extract_threshold_followup(q_raw)
        has_threshold = threshold_info.get("value") is not None and threshold_info.get("operator") is not None
        if has_threshold:
            explicit_metric = None
            if any(k in q_raw for k in ["ครู", "อาจารย์", "บุคลากร"]):
                explicit_metric = "teachers"
            elif any(k in q_raw for k in ["นักเรียน", "ผู้เรียน", "เด็ก"]):
                explicit_metric = "students"

            followup_like = q_raw.startswith(("แล้ว", "งั้น", "ถ้า", "แล้วถ้า")) or any(k in q_raw for k in q_followup_markers)
            has_scope_in_question = any(k in q_raw for k in ["จังหวัด", "อำเภอ", "เขต", "ตำบล", "แขวง", "ภาค"])
            ctx = context or {}
            has_context_scope = bool(ctx.get("last_province") or ctx.get("last_district") or ctx.get("last_region"))

            if followup_like or (not has_scope_in_question and has_context_scope):
                params: Dict[str, Any] = {
                    "operator": threshold_info["operator"],
                    "value": threshold_info["value"],
                    "limit": 20,
                }

                metric = explicit_metric
                if not metric:
                    active = ctx.get("last_active_query") or {}
                    if isinstance(active, dict):
                        active_params = active.get("params", {}) or {}
                        if active.get("name") == "filter_schools":
                            metric = active_params.get("metric")
                params["metric"] = metric or "students"

                province = self._extract_province(q_raw) or ctx.get("last_province")
                district = self._extract_district(q_raw) or ctx.get("last_district")
                region = self._extract_region(q_raw) or ctx.get("last_region")
                if province:
                    params["province"] = province
                if district:
                    params["district"] = district
                if region and not province:
                    params["region"] = region

                logger.info(f"⚡ Quick-path THRESHOLD FOLLOW-UP: {params}")
                return [{"name": "filter_schools", "params": params}]


        # ══════════════════════════════════════════════════════════════
        # LLM-FIRST: Only keep concept groups that LLM can't Know
        # All other routing delegated to LLM structured extraction
        # ══════════════════════════════════════════════════════════════
        q_raw = (question or "")

        # ── Quick-path: Concept group "3 จังหวัดชายแดนภาคใต้" ──
        southern_border_kws = ["3 จังหวัดชายแดน", "สามจังหวัดชายแดน", "3จังหวัดชายแดน", "จังหวัดชายแดนภาคใต้"]
        if any(k in q_raw for k in southern_border_kws):
            border_provinces = "ปัตตานี,ยะลา,นราธิวาส"
            has_students = any(k in q_raw for k in ["นักเรียน", "ผู้เรียน"])
            has_teachers = any(k in q_raw for k in ["ครู", "อาจารย์", "บุคลากร"])
            has_schools = any(k in q_raw for k in ["โรงเรียน", "สถานศึกษา", "กี่โรง", "กี่แห่ง"])
            if has_students:
                m = "students"
            elif has_teachers:
                m = "teachers"
            elif has_schools or "โรงเรียน" in q_raw:
                m = "schools"
            else:
                m = "all"
            logger.info(f"⚡ Quick-path CONCEPT GROUP (3 จังหวัดชายแดน): metric={m}")
            return [{"name": "compare_provinces", "params": {"provinces": border_provinces, "metrics": m}}]

        # ── Quick-path: EEC concept group ──
        eec_kws = ["eec", "อีอีซี", "EEC", "ระเบียงเศรษฐกิจ"]
        if any(k in q_raw.lower() for k in eec_kws):
            eec_provinces = "ชลบุรี,ระยอง,ฉะเชิงเทรา"
            has_students = any(k in q_raw for k in ["นักเรียน", "ผู้เรียน"])
            has_teachers = any(k in q_raw for k in ["ครู", "อาจารย์", "บุคลากร"])
            has_schools = any(k in q_raw for k in ["โรงเรียน", "สถานศึกษา", "กี่โรง", "กี่แห่ง"])
            if has_students:
                m = "students"
            elif has_teachers:
                m = "teachers"
            elif has_schools or "โรงเรียน" in q_raw:
                m = "schools"
            else:
                m = "all"
            logger.info(f"⚡ Quick-path CONCEPT GROUP (EEC): metric={m}")
            return [{"name": "compare_provinces", "params": {"provinces": eec_provinces, "metrics": m}}]

        # ── Quick-path: National summary ──
        national_kws = ['ระดับประเทศ', 'ทั้งประเทศ', 'ภาพรวมทั้งประเทศ', 'สรุประดับประเทศ',
                        'ระดับชาติ', 'ประเทศไทยทั้งหมด', 'ภาพรวมประเทศ', 'สรุปภาพรวมประเทศ']
        if any(k in q_raw for k in national_kws):
            ns_params = {}
            # Extract year if present
            import re as _re
            year_m = _re.search(r'ปี(?:การศึกษา)?\s*(\d{2,4})', q_raw)
            if year_m:
                from ..core.constants import YEAR_ALIASES, AVAILABLE_YEARS
                y = year_m.group(1)
                y = YEAR_ALIASES.get(y, y)
                if y in AVAILABLE_YEARS:
                    ns_params["year"] = y
            logger.info(f"⚡ Quick-path NATIONAL SUMMARY: {ns_params}")
            return [{"name": "get_national_summary", "params": ns_params}]

        # ══════════════════════════════════════════════════════════════
        # LLM STRUCTURED EXTRACTION — primary tool selection
        # ══════════════════════════════════════════════════════════════


        structured = extract_query_structured_via_llm(question, self.llm, context=context or {})
        confidence = structured.get("confidence")
        data_required = bool(structured.get("data_required"))

        if structured.get("needs_clarification"):
            msg = structured.get("clarification_question") or "ขอรายละเอียดเพิ่มอีกนิดได้ไหมครับ"
            pending_tool = None
            if structured.get("multi_step"):
                pending_tool = {"name": "__multi_step__", "params": {"plan": structured.get("multi_step")}}
            elif structured.get("tool"):
                pending_tool = {"name": structured.get("tool"), "params": structured.get("params") or {}}
            elif structured.get("intent") and get_tool_by_name(structured.get("intent")):
                pending_tool = {"name": structured.get("intent"), "params": structured.get("params") or {}}
            return [{"name": "__ask_back__", "params": {"message": msg, "pending_tool": pending_tool}}]

        # Multi-step reasoning path
        if structured.get("multi_step"):
            if confidence is not None and confidence < self.min_confidence:
                return [{"name": "__ask_back__", "params": {"message": "ขอรายละเอียดเพิ่มอีกนิดได้ไหมครับ เพื่อคำนวณให้ถูกต้อง", "pending_tool": None}}]
            return [{"name": "__multi_step__", "params": {"plan": structured.get("multi_step")}}]

        tool = structured.get("tool")
        params = structured.get("params") or {}

        # Normalize tool via intent fallback (if any)
        if not tool and structured.get("intent"):
            tool = structured.get("intent")

        # Enforce data-query policy: do not allow general_chat for data-required questions
        if data_required and (tool is None or tool == "general_chat"):
            # If intent looks like a tool, prefer it
            intent_tool = structured.get("intent")
            if intent_tool and get_tool_by_name(intent_tool):
                tool = intent_tool
            else:
                msg = "คำถามนี้ต้องใช้ข้อมูลจากฐานข้อมูลครับ ช่วยระบุให้ชัดขึ้นได้ไหมครับ เช่น จังหวัดหรือชื่อโรงเรียน"
                return [{"name": "__ask_back__", "params": {"message": msg, "pending_tool": None}}]

        # If LLM says this is NOT a data query, force general_chat to avoid DB/ask-back loops
        if data_required is False:
            tool = "general_chat"
            params = {}

        if confidence is not None and confidence < self.min_confidence and tool != "general_chat":
            # If scope is already clear, proceed to reduce unnecessary ask-back
            has_scope = any(params.get(k) for k in ["province", "region", "school_name", "district", "agency"])
            if not has_scope:
                pending_tool = {"name": tool, "params": params} if tool else None
                return [{"name": "__ask_back__", "params": {"message": "ขอรายละเอียดเพิ่มอีกนิดได้ไหมครับ เพื่อให้ตอบได้ตรงจุด", "pending_tool": pending_tool}}]

        if not tool:
            return [{"name": "__ask_back__", "params": {"message": "ขอรายละเอียดเพิ่มอีกนิดได้ไหมครับ (เช่น จังหวัดหรือชื่อโรงเรียน)", "pending_tool": None}}]

        if tool != "general_chat" and not get_tool_by_name(tool):
            return [{"name": "__ask_back__", "params": {"message": "ขอรายละเอียดเพิ่มอีกนิดได้ไหมครับ เพื่อเลือกเครื่องมือให้ถูกต้อง", "pending_tool": None}}]

        params = self._sanitize_structured_params(tool, params)

        # Enrich: inject person_type if LLM forgot (common for "ข้าราชการครู กี่คน")
        if tool == "count_teachers" and not params.get("person_type"):
            pt = self._extract_person_type(question)
            if pt:
                params["person_type"] = pt
                logger.info(f"👔 Enriched person_type from question: {pt}")

        # Route-guard: fix obvious misrouting (e.g., province summary vs school detail)
        tool, params = self._route_guard(question, tool, params)
        clarification = self._build_clarification(tool, params)
        if clarification:
            pending_tool = {"name": tool, "params": params} if tool else None
            return [{"name": "__ask_back__", "params": {"message": clarification, "pending_tool": pending_tool}}]

        return [{"name": tool, "params": params}]
    def _enrich_scope_params(self, question: str, tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """เติม scope จากข้อความผู้ใช้เพื่อกันกรณี LLM ส่งพารามิเตอร์ไม่ครบ"""
        enriched = dict(params or {})
        q = question or ""

        if not enriched.get("province"):
            province = self._extract_province(q)
            if province:
                enriched["province"] = province
        if not enriched.get("district"):
            district = self._extract_district(q)
            if district:
                enriched["district"] = district
        if not enriched.get("region"):
            region = self._extract_region(q)
            if region:
                enriched["region"] = region

        if tool == "ranking":
            q_lower = q.lower()
            scope = enriched.get("scope")
            asks_region_entity = (
                any(k in q for k in ["ภาคไหน", "ภาคใด", "ภูมิภาคไหน", "ภูมิภาคใด"])
                or ("ระดับภาค" in q and not any(k in q for k in ["จังหวัด", "อำเภอ", "ตำบล", "โรงเรียน"]))
            )

            # Infer ranking metric/order when LLM params are incomplete
            ratio_kws = [
                "อัตราส่วน", "ครูต่อ", "ครูต่อนักเรียน", "นักเรียนต่อครู", "ต่อครู", "ต่อเด็ก",
                "ไม่ทั่วถึง", "ดูแลเด็ก", "ขาดแคลนครู", "ครูน้อยเมื่อเทียบกับเด็ก"
            ]
            if any(k in q for k in ratio_kws):
                enriched["metric"] = "ratio"
            elif not enriched.get("metric"):
                if any(k in q for k in ["ครู", "อาจารย์", "บุคลากร"]):
                    enriched["metric"] = "teachers"
                elif any(k in q for k in ["นักเรียน", "ผู้เรียน", "เด็ก"]):
                    enriched["metric"] = "students"
                else:
                    enriched["metric"] = "schools"

            if not enriched.get("order"):
                if any(k in q for k in ["น้อยที่สุด", "ต่ำที่สุด", "ต่ำสุด", "น้อยสุด", "รั้งท้าย"]):
                    enriched["order"] = "least"
                else:
                    enriched["order"] = "most"

            if enriched.get("metric") == "teachers" and not enriched.get("person_type"):
                person_type = self._extract_person_type(q)
                if person_type:
                    pt_aliases = {
                        "ครูอัตราจ้าง": "ลูกจ้างชั่วคราว",
                        "อัตราจ้าง": "ลูกจ้างชั่วคราว",
                        "ครูจ้าง": "ลูกจ้างชั่วคราว",
                        "ข้าราชการ": "ข้าราชการครู",
                    }
                    enriched["person_type"] = pt_aliases.get(person_type, person_type)

            if not scope:
                if asks_region_entity:
                    enriched["scope"] = "region"
                elif any(k in q for k in ["ตำบล", "แขวง"]):
                    enriched["scope"] = "subdistrict"
                elif any(k in q for k in ["อำเภอ", "เขต"]):
                    enriched["scope"] = "district"
                elif "จังหวัด" in q:
                    enriched["scope"] = "province"

            is_country_scope = any(k in q for k in ["ทั่วประเทศ", "ทั้งประเทศ", "ระดับประเทศ"])
            if is_country_scope and enriched.get("scope") == "province":
                enriched.pop("province", None)
                enriched.pop("region", None)

            if enriched.get("scope") == "region":
                # Region ranking should not be narrowed by stale province context
                enriched.pop("province", None)
            if (
                enriched.get("scope") in ["district", "subdistrict"]
                and not enriched.get("province")
                and not enriched.get("region")
            ):
                province = self._extract_province(q)
                if province:
                    enriched["province"] = province

        if tool == "filter_schools":
            if not enriched.get("metric"):
                enriched["metric"] = "teachers" if "ครู" in q else "students"
            if not enriched.get("operator"):
                if any(k in q for k in ["มากกว่า", "เกิน", "สูงกว่า"]):
                    enriched["operator"] = "gt"
                elif any(k in q for k in ["เท่ากับ", "พอดี"]):
                    enriched["operator"] = "eq"
                elif any(k in q for k in ["น้อยกว่า", "ต่ำกว่า", "ไม่เกิน"]):
                    enriched["operator"] = "lt"
            if enriched.get("value") is None:
                m = re.search(r'(\d[\d,]*)', q)
                if m:
                    try:
                        enriched["value"] = int(m.group(1).replace(",", ""))
                    except Exception:
                        pass

        return enriched
    def _route_guard(self, question: str, tool: str, params: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        """Lightweight guard to fix common tool mis-selections without overriding valid intents."""
        if not tool:
            return tool, params

        # Never override these tools — they are intentionally selected by LLM
        PROTECTED_TOOLS = {"ranking", "compare_provinces", "filter_schools", "find_best_ratio_schools",
                           "ranking_by_agency", "ranking_subdistricts", "compare",
                           "count_students", "count_teachers", "count_schools"}
        if tool in PROTECTED_TOOLS:
            return tool, self._enrich_scope_params(question, tool, params)

        q = (question or "")
        q_lower = q.lower()

        has_students = any(k in q for k in ["นักเรียน", "ผู้เรียน", "เด็ก"])
        has_teachers = any(k in q for k in ["ครู", "อาจารย์", "บุคลากร"])
        has_summary = any(k in q for k in ["สรุป", "ภาพรวม", "ทั้งหมด", "รวม"])
        has_system = any(k in q for k in ["ในระบบ", "นอกระบบ", "ระบบการศึกษา"])
        has_area = any(k in q for k in ["สพป", "สพม", "เขตพื้นที่", "เขตการศึกษา"])
        has_area_detail = any(k in q for k in ["ครอบคลุม", "อำเภออะไรบ้าง", "อำเภอใด", "อำเภอไหน"])
        has_grade = any(k in q for k in ["ระดับชั้น", "ชั้นไหน", "ระดับชั้นไหน", "ป.", "ม.", "อนุบาล", "ปวช", "ปวส"])
        has_gender_ratio = any(k in q for k in ["สัดส่วนเพศ", "อัตราส่วนเพศ"])

        # ── Ranking guard: force ranking tool when question clearly asks for top/bottom ──
        rank_kws = ["มากที่สุด", "น้อยที่สุด", "เยอะที่สุด", "สูงสุด", "ต่ำสุด", "อันดับ", "top"]
        if any(k in q for k in rank_kws):
            least_kws = ["น้อยที่สุด", "ต่ำสุด", "ต่ำที่สุด", "รั้งท้าย"]
            order = "least" if any(k in q for k in least_kws) else "most"
            ratio_kws = [
                "อัตราส่วน", "ครูต่อ", "ครูต่อนักเรียน", "ครูต่อเด็ก", "นักเรียนต่อครู",
                "ไม่ทั่วถึง", "ดูแลเด็ก", "ขาดแคลนครู", "ครูน้อยเมื่อเทียบกับเด็ก"
            ]
            if any(k in q for k in ratio_kws):
                metric = "ratio"
            elif has_teachers:
                metric = "teachers"
            elif has_students:
                metric = "students"
            else:
                metric = "schools"

            # limit from text (e.g., "5 อันดับ", "Top 10")
            limit = params.get("limit")
            if not limit:
                m = re.search(r'(?:top\\s*(\\d+))|(\\d+)\\s*อันดับ', q_lower)
                if m:
                    limit = int(m.group(1) or m.group(2))

            province = params.get("province") or self._extract_province(q)
            region = params.get("region") or self._extract_region(q)
            person_type = params.get("person_type") or self._extract_person_type(q)
            if isinstance(person_type, str):
                person_type = {
                    "ครูอัตราจ้าง": "ลูกจ้างชั่วคราว",
                    "อัตราจ้าง": "ลูกจ้างชั่วคราว",
                    "ครูจ้าง": "ลูกจ้างชั่วคราว",
                    "ข้าราชการ": "ข้าราชการครู",
                }.get(person_type, person_type)

            if any(k in q for k in ["ตำบล", "แขวง"]):
                # Prefer dedicated subdistrict ranking when province is known.
                # If only region is known, use generic ranking(scope=subdistrict, region=...)
                if province:
                    return "ranking_subdistricts", {
                        "province": province,
                        "district": params.get("district"),
                        "metric": metric,
                        "order": order,
                        "limit": limit or 5
                    }
                ranking_params = {
                    "metric": metric,
                    "order": order,
                    "scope": "subdistrict",
                    "limit": limit or 5
                }
                if region:
                    ranking_params["region"] = region
                return "ranking", ranking_params

            asks_region_entity = (
                any(k in q for k in ["ภาคไหน", "ภาคใด", "ภูมิภาคไหน", "ภูมิภาคใด"])
                or ("ระดับภาค" in q and not any(k in q for k in ["จังหวัด", "อำเภอ", "ตำบล", "โรงเรียน"]))
            )

            if asks_region_entity:
                scope = "region"
            elif any(k in q for k in ["อำเภอ", "เขต"]):
                scope = "district"
            elif "โรงเรียน" in q:
                scope = "school"
            else:
                scope = "province"

            ranking_params = {
                "metric": metric,
                "order": order,
                "scope": scope,
                "limit": limit or 5
            }
            if metric == "teachers" and person_type:
                ranking_params["person_type"] = person_type
            if scope == "region":
                # "ภาคไหน..." should rank all regions (not constrain to one region/province)
                ranking_params.pop("province", None)
                ranking_params.pop("region", None)
            else:
                if province:
                    ranking_params["province"] = province
                if region:
                    ranking_params["region"] = region

            return "ranking", ranking_params

        # If asking for both students + teachers at province scope (WITHOUT school name), use province summary
        if (has_students and has_teachers) and params.get("province") and not params.get("school_name"):
            return "get_province_summary", {"province": params.get("province")}

        # System type queries (in-system/out-of-system)
        if has_system:
            system_type = None
            if "ในระบบ" in q:
                system_type = "ในระบบ"
            elif "นอกระบบ" in q:
                system_type = "นอกระบบ"
            new_params = {"province": params.get("province"), "district": params.get("district")}
            if system_type:
                new_params["system_type"] = system_type
            return "count_by_system_type", new_params

        # Education area queries (สพป./สพม.)
        if has_area:
            if has_area_detail and params.get("area_name"):
                return "get_education_area_info", {"area_name": params.get("area_name")}
            return "search_education_areas", {
                "area_name": params.get("area_name"),
                "province": params.get("province"),
                "district": params.get("district")
            }

        # Gender ratio (students overview)
        if has_gender_ratio and not params.get("school_name"):
            return "analyze_gender_ratio", {
                "province": params.get("province"),
                "district": params.get("district")
            }

        # Grade distribution (area/school)
        if has_grade:
            return "get_grade_distribution", {
                "province": params.get("province"),
                "district": params.get("district"),
                "school_name": params.get("school_name"),
                "grade": params.get("grade")
            }

        # If tool is school detail but missing school_name, try to map to province summary when scope exists
        if tool == "get_school_full_details" and not params.get("school_name"):
            prov = params.get("province") or self._extract_province(q)
            if prov and (has_summary or has_students or has_teachers):
                return "get_province_summary", {"province": prov}

        # If question is clearly about province-wide ratio but tool picked school detail
        if tool == "get_school_full_details" and not params.get("school_name") and "อัตราส่วน" in q:
            if params.get("province"):
                return "get_ratio", {"province": params.get("province")}

        return tool, params
    def _sanitize_structured_params(self, tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = dict(params or {})

        # Normalize metric/order/scope
        metric_map = {
            "นักเรียน": "students",
            "ผู้เรียน": "students",
            "students": "students",
            "ครู": "teachers",
            "บุคลากร": "teachers",
            "teachers": "teachers",
            "โรงเรียน": "schools",
            "สถานศึกษา": "schools",
            "schools": "schools",
            "อัตราส่วน": "ratio",
            "ratio": "ratio",
        }
        order_map = {
            "มากที่สุด": "most",
            "สูงสุด": "most",
            "เยอะที่สุด": "most",
            "เยอะสุด": "most",
            "most": "most",
            "desc": "most",
            "descending": "most",
            "น้อยที่สุด": "least",
            "ต่ำสุด": "least",
            "least": "least",
            "asc": "least",
            "ascending": "least",
            "ดีที่สุด": "best",
            "แย่ที่สุด": "worst",
            "worst": "worst",
            "best": "best",
        }
        scope_map = {
            "จังหวัด": "province",
            "อำเภอ": "district",
            "เขต": "district",
            "โรงเรียน": "school",
            "ภาค": "region",
            "province": "province",
            "district": "district",
            "school": "school",
            "region": "region",
        }
        operator_map = {
            "lt": "lt",
            "gt": "gt",
            "eq": "eq",
            "lte": "lte",
            "gte": "gte",
            "น้อยกว่า": "lt",
            "มากกว่า": "gt",
            "เท่ากับ": "eq",
            "ไม่เกิน": "lte",
            "อย่างน้อย": "gte",
        }

        if cleaned.get("metric") in metric_map:
            cleaned["metric"] = metric_map[cleaned["metric"]]
        if isinstance(cleaned.get("metric"), str) and cleaned.get("metric") in metric_map:
            cleaned["metric"] = metric_map[cleaned["metric"]]

        if cleaned.get("order") in order_map:
            cleaned["order"] = order_map[cleaned["order"]]

        if cleaned.get("scope") in scope_map:
            cleaned["scope"] = scope_map[cleaned["scope"]]
        # Keep scope="region" for ranking (used by questions like "ภาคไหนมี...มากที่สุด")

        if cleaned.get("operator") in operator_map:
            cleaned["operator"] = operator_map[cleaned["operator"]]

        if isinstance(cleaned.get("person_type"), str):
            person_type_map = {
                "ครูอัตราจ้าง": "ลูกจ้างชั่วคราว",
                "อัตราจ้าง": "ลูกจ้างชั่วคราว",
                "ครูจ้าง": "ลูกจ้างชั่วคราว",
                "ข้าราชการ": "ข้าราชการครู",
                "พนง.ราชการ": "พนักงานราชการ",
            }
            cleaned["person_type"] = person_type_map.get(cleaned["person_type"].strip(), cleaned["person_type"].strip())

        # Ensure limit is int and reasonable
        if "limit" in cleaned and cleaned["limit"] is not None:
            try:
                cleaned["limit"] = int(cleaned["limit"])
            except Exception:
                cleaned["limit"] = None
        if cleaned.get("limit") is not None:
            cleaned["limit"] = max(1, min(cleaned["limit"], 50))

        # Normalize compare_provinces provinces list
        if tool == "compare_provinces":
            provinces = cleaned.get("provinces")
            if isinstance(provinces, str):
                provinces = [p.strip() for p in provinces.replace(";", ",").split(",") if p.strip()]
                cleaned["provinces"] = provinces

        return cleaned
    def _build_clarification(self, tool: str, params: Dict[str, Any]) -> Optional[str]:
        if tool == "get_school_full_details" and not params.get("school_name"):
            return "ต้องการรายละเอียดของโรงเรียนไหนครับ"
        if tool == "compare" and (not params.get("entity1") or not params.get("entity2")):
            return "ต้องการเปรียบเทียบระหว่างอะไรกับอะไรครับ"
        if tool == "ranking" and (not params.get("metric") or not params.get("order")):
            return "ต้องการจัดอันดับเรื่องอะไร และมากที่สุดหรือน้อยที่สุดครับ"
        if tool == "ranking_subdistricts":
            if not params.get("province") or not params.get("metric") or not params.get("order"):
                return "ต้องการจัดอันดับตำบลในจังหวัดไหน และจัดอันดับเรื่องอะไรครับ"
        if tool == "get_ratio" and not params.get("school_name") and not params.get("province"):
            return "ต้องการอัตราส่วนของโรงเรียนไหนหรือจังหวัดไหนครับ"
        if tool in ["list_schools", "search_schools"]:
            if not params.get("school_name") and not params.get("province") and not params.get("region") and not params.get("district") and not params.get("agency"):
                return "ต้องการค้นหาในพื้นที่ไหน หรือชื่อโรงเรียนอะไรครับ"
        if tool == "search_education_areas":
            if not params.get("province") and not params.get("area_name") and not params.get("district"):
                return "ต้องการค้นหาเขตพื้นที่ของจังหวัดไหน หรือชื่อเขตอะไรครับ"
            if params.get("district") in ["เมือง"] and not params.get("province"):
                return "อำเภอเมืองของจังหวัดไหนครับ"
            if params.get("area_name") and params.get("area_name") in ["สพป.", "สพม.", "สพป", "สพม"]:
                return "ต้องการเขตพื้นที่ของจังหวัดไหนครับ"
        if tool == "get_grade_distribution":
            if not params.get("province") and not params.get("district") and not params.get("school_name"):
                return "ต้องการดูระดับชั้นของพื้นที่ไหน หรือโรงเรียนไหนครับ"
            if params.get("grade") in ["ป", "ม", "อ", "ป.", "ม.", "อ."]:
                return "ต้องการระดับชั้นไหนครับ เช่น ป.1 หรือ ม.3"
        if tool == "get_province_summary" and not params.get("province"):
            return "ต้องการสรุปจังหวัดไหนครับ"
        if tool == "get_district_summary" and (not params.get("province") or not params.get("district")):
            return "ต้องการสรุปอำเภอไหนในจังหวัดใดครับ"
        if tool == "compare_provinces" and not params.get("provinces"):
            return "ต้องการเปรียบเทียบจังหวัดไหนบ้างครับ"
        if tool == "find_nearby_schools" and (not params.get("latitude") or not params.get("longitude")):
            return "ต้องการค้นหาใกล้พิกัดไหนครับ (ขอละติจูดและลองจิจูด)"
        if tool == "advanced_school_search":
            has_numeric = any(params.get(k) is not None for k in ["min_students", "max_students", "min_teachers", "max_teachers"])
            if not has_numeric:
                return "ต้องการค้นหาโรงเรียนด้วยเงื่อนไขตัวเลขอะไรครับ เช่น นักเรียนมากกว่า 500 คน"
        if tool == "filter_schools":
            if not params.get("metric") or not params.get("operator") or params.get("value") is None:
                return "ต้องการกรองด้วยเงื่อนไขอะไรครับ เช่น นักเรียนน้อยกว่า 100 คน"
        return None
    def _format_ask_back(self, message: str) -> str:
        msg = (message or "").strip()
        if not msg:
            msg = "ขอรายละเอียดเพิ่มอีกนิดได้ไหมครับ"
        if not msg.endswith("ครับ"):
            msg += "ครับ"
        return msg
    def _ensure_ratio_tool(self, question: str, tool_calls: List[Dict[str, Any]], context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """If question asks for ratio, ensure get_ratio is included with best-available params."""
        if not tool_calls:
            return tool_calls

        ratio_keywords = ["อัตราส่วน", "ต่อครู", "ครูต่อนักเรียน", "นักเรียนต่อครู", "ratio"]
        if not any(k in question for k in ratio_keywords):
            return tool_calls

        if any(t.get("name") == "get_ratio" for t in tool_calls):
            return tool_calls

        params = {}
        # Try to reuse params from other tool calls
        for t in tool_calls:
            p = t.get("params", {})
            if p.get("school_name") and not params.get("school_name"):
                params["school_name"] = p.get("school_name")
            if p.get("province") and not params.get("province"):
                params["province"] = p.get("province")

        # Fallback to context if still missing
        if context:
            if not params.get("school_name"):
                params["school_name"] = context.get("last_school_name") or context.get("current_school")
            if not params.get("province"):
                params["province"] = context.get("last_province") or context.get("current_province")

        tool_calls.append({"name": "get_ratio", "params": params})
        logger.info("➕ Added get_ratio tool for ratio query")
        return tool_calls
    def _enrich_tool_params(self, question: str, tool_calls: List[Dict], context: Dict = None) -> List[Dict]:
        """Enrich LLM tool selections with context from previous turns ONLY.
        
        LLM-FIRST APPROACH:
        - LLM is now responsible for extracting entities (province, school_name) directly
        - This method ONLY handles context injection for follow-up questions
        - No more regex extraction or garbage filtering - LLM handles everything
        """
        question_region = self._extract_region(question)
        q_text = question or ""
        q_norm = q_text.replace(" ", "")
        follow_kws = ["แล้ว", "ต่อ", "อีก", "เพิ่ม", "ขอรายละเอียด", "รายละเอียด", "พิกัด", "ที่ไหน", "เบอร์ติดต่อ", "ครูกี่", "นักเรียนกี่", "ข้อมูล", "เฉพาะ", "แยก"]
        starts_followup = q_text.startswith(("แล้ว", "งั้น", "ถ้า", "กรณี", "แล้วถ้า", "เอาเฉพาะ"))
        is_followup = (len(q_text) <= 200 and any(k in q_text for k in follow_kws)) or starts_followup
        
        # ── Pronoun reference detection ──────────────────────────────────
        # จังหวัดนี้ / โรงเรียนนี้ / ของจังหวัดนี้ / ในจังหวัดนี้ etc.
        province_pronouns = ["จังหวัดนี้", "ในจังหวัดนี้", "ของจังหวัดนี้", "จ.นี้", "จังหวัดเดิม", "จังหวัดเดียวกัน"]
        school_pronouns = ["โรงเรียนนี้", "ของโรงเรียนนี้", "ในโรงเรียนนี้", "ร.ร.นี้", "สถานศึกษานี้"]
        has_province_pronoun = any(p in q_text for p in province_pronouns)
        has_school_pronoun = any(p in q_text for p in school_pronouns)
        is_pronoun_ref = has_province_pronoun or has_school_pronoun
        
        # Pronoun references should ALWAYS trigger context injection
        if is_pronoun_ref:
            is_followup = True
        
        # Resolve pronouns from context — inject actual names
        ctx_province = None
        ctx_school = None
        if context:
            ctx_province = context.get('last_province') or context.get('current_province')
            ctx_school = context.get('last_school_name') or context.get('current_school')
        
        if has_province_pronoun and ctx_province:
            logger.info(f"🔗 Pronoun 'จังหวัดนี้' resolved to: {ctx_province}")
        if has_school_pronoun and ctx_school:
            logger.info(f"🔗 Pronoun 'โรงเรียนนี้' resolved to: {ctx_school}")
        
        for tool in tool_calls:
            params = tool.get('params', {})
            
            # Tools that accept school_name (specific school only)
            school_specific_tools = ['get_school_full_details', 'get_grade_distribution']
            # Tools that accept ONLY province (not school_name)
            province_only_tools = ['list_schools', 'advanced_school_search', 'filter_schools']
            aggregation_tools = ['count_students', 'count_teachers', 'count_schools']
            # Pronoun reference → also inject into ranking/filter (not just follow-up tools)
            skip_context_tools = ['compare', 'general_chat']
            if not is_pronoun_ref:
                skip_context_tools.append('ranking')
            
            # Context injection for follow-up questions ONLY
            if context and tool['name'] not in skip_context_tools and is_followup:
                _ctx_school = ctx_school
                _ctx_province = ctx_province
                
                if not params.get('school_name') and _ctx_school and tool['name'] in school_specific_tools:
                    if _ctx_school.replace("โรงเรียน", "").replace(" ", "") in q_norm or is_followup:
                        params['school_name'] = _ctx_school
                        logger.info(f"💉 Injected context school_name: {_ctx_school}")

                # Inject province from context (or pronoun-resolved province)
                if not params.get('province') and _ctx_province:
                    if question_region:
                        # If user asked about a region, don't force a province from context
                        pass
                    elif has_province_pronoun:
                        # Pronoun reference → ALWAYS inject province regardless of tool type
                        params['province'] = _ctx_province
                        logger.info(f"💉 Injected province from pronoun 'จังหวัดนี้': {_ctx_province}")
                    else:
                        # Regular follow-up: only inject for province-aware tools
                        if not params.get('school_name'):
                            province_aware_tools = school_specific_tools + province_only_tools + aggregation_tools
                            if isinstance(_ctx_province, str) and tool['name'] in province_aware_tools:
                                params['province'] = _ctx_province
                                logger.info(f"💉 Injected context province: {_ctx_province}")

            # Normalize region if LLM put it into province
            if params.get('province') and not params.get('region'):
                if isinstance(params.get('province'), str) and (params['province'].startswith("ภาค") or params['province'] in REGIONS):
                    params['region'] = params['province']
                    params.pop('province', None)

            # Inject region from question when missing
            if question_region and not params.get('region'):
                region_tools = ['count_students', 'count_teachers', 'count_schools', 'list_schools',
                                'filter_schools', 'ranking', 'search_schools', 'advanced_school_search']
                if tool['name'] in region_tools:
                    params['region'] = question_region
                    logger.info(f"💉 Injected region from question: {question_region}")

            # Inject region from CONTEXT (memory) for follow-up queries when missing
            if not params.get('region') and not question_region and context and is_followup:
                ctx_region = context.get('last_region')
                if ctx_region:
                    region_tools = ['count_students', 'count_teachers', 'count_schools',
                                    'list_schools', 'ranking', 'advanced_school_search']
                    if tool['name'] in region_tools:
                        params['region'] = ctx_region
                        logger.info(f"💉 Injected region from context (follow-up): {ctx_region}")

            # Inject district from question when missing (non-followup safe)
            if not params.get('district'):
                question_district = self._extract_district(question)
                if question_district:
                    district_tools = [
                        'count_students', 'count_teachers', 'count_schools',
                        'list_schools', 'search_schools', 'filter_schools',
                        'get_grade_distribution', 'analyze_gender_ratio',
                        'count_by_system_type'
                    ]
                    if tool['name'] in district_tools:
                        params['district'] = question_district
                        logger.info(f"💉 Injected district from question: {question_district}")

            # Inject year from question or context memory when missing
            if not params.get('year'):
                import re
                year_match = re.search(r'ปี(?:การศึกษา)?\s*(\d{2,4})', q_text)
                if year_match:
                    from .core.constants import YEAR_ALIASES, AVAILABLE_YEARS
                    year_str = year_match.group(1)
                    if year_str in YEAR_ALIASES:
                        params['year'] = YEAR_ALIASES[year_str]
                        logger.info(f"💉 Injected year from question: {params['year']}")
                    elif len(year_str) == 4 and year_str in AVAILABLE_YEARS:
                        params['year'] = year_str
                        logger.info(f"💉 Injected year from question: {params['year']}")
                elif context and is_followup:
                    ctx_year = context.get('last_year')
                    if ctx_year:
                        params['year'] = ctx_year
                        logger.info(f"💉 Injected year from context (follow-up): {ctx_year}")

            # Normalize ranking params when LLM is vague (e.g., "จังหวัดที่มีโรงเรียนมากที่สุด")
            if tool['name'] == "ranking":
                q_lower = question.lower()
                rank_kws = ['มากที่สุด', 'น้อยที่สุด', 'อันดับ', 'top', 'สูงสุด', 'ต่ำสุด', 'เยอะที่สุด', 'เยอะสุด', 'มากสุด', 'น้อยสุด']
                if any(kw in q_lower for kw in rank_kws):
                    has_student = any(kw in q_lower for kw in ['นักเรียน', 'เด็ก', 'นักศึกษา'])
                    has_teacher = any(kw in q_lower for kw in ['ครู', 'อาจารย์', 'บุคลากร'])
                    has_school_kw = any(kw in q_lower for kw in ['โรงเรียน', 'สถานศึกษา', 'สถาบัน'])

                    if not has_student and not has_teacher and has_school_kw:
                        params['metric'] = "schools"
                        if "จังหวัด" in q_lower and not params.get('province'):
                            params['scope'] = "province"
                        else:
                            params.setdefault('scope', "school")
                    # If ranking provinces by school count, drop province constraint
                    if params.get('metric') == "schools" and params.get('scope') == "province":
                        params.pop('province', None)
            
            tool['params'] = params
        
        return tool_calls
    def _parse_tool_calls(self, response_text: str) -> List[Dict[str, Any]]:
        """Parse tool calls from LLM response"""
        try:
            # Check for "no tool" type responses - treat as general query
            no_tool_indicators = ['no tool', 'ไม่มี tool', 'cannot', 'ไม่สามารถ', '[]']
            if any(indicator.lower() in response_text.lower() for indicator in no_tool_indicators):
                logger.info("🌐 LLM indicated no tools needed - treating as general query")
                return []
            
            # Try to find JSON array candidates (non-greedy to handle multiple blocks)
            # e.g. "I will use [search] tool... [{"name": ...}]"
            candidates = re.findall(r'(\[[\s\S]*?\])', response_text)
            
            for json_str in candidates:
                try:
                    # Clean invalid escapes common in LLM output
                    # Use regex to remove backslash before non-escape characters
                    # Valid JSON escapes: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
                    # Invalid (LLM artifacts): \., \(, \), \', \-  etc.
                    json_str_clean = re.sub(r'\\([^"\\\/bfnrtu])', r'\1', json_str)
                    
                    parsed = json.loads(json_str_clean)
                    
                    if isinstance(parsed, list):
                        # Validate parsed tools have valid names
                        valid_tools = []
                        for p in parsed:
                             if isinstance(p, dict) and get_tool_by_name(p.get("name")):
                                 valid_tools.append(p)
                                 
                        if valid_tools:
                            logger.info(f"✅ Parsed tools successfully: {[t['name'] for t in valid_tools]}")
                            return valid_tools
                except Exception as e:
                    logger.debug(f"⚠️ Candidate parsing failed: {e}")
                    continue
            
            # If no candidates worked, fall back to trying the whole text
            try:
                # Also clean the whole text response
                response_text_clean = response_text.replace("\\'", "'").replace(r"\.", ".").replace(r"\(", "(").replace(r"\)", ")")
                parsed = json.loads(response_text_clean)
                if isinstance(parsed, list):
                     return [p for p in parsed if get_tool_by_name(p.get("name"))]
            except Exception as e:
                logger.debug(f"⚠️ Fallback parsing failed: {e} | Cleaned: {response_text_clean}")
                pass
            
            logger.warning("⚠️ No JSON array found in LLM response")
            logger.warning(f"🐛 Raw LLM Response: {response_text}")
            return []
            
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ Failed to parse tool calls: {e}")
            logger.debug(f"Response was: {response_text[:500]}")
            return []
        except Exception as e: # Catch other potential errors during parsing/validation
            logger.warning(f"⚠️ Failed to parse tool calls: {e}")
            logger.warning(f"🐛 Raw LLM Response: {response_text}")
            return []
    def _infer_tools_from_keywords(self, question: str, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Fallback: Infer tools from keywords when LLM fails"""
        question_lower = question.lower()
        
        # =========================================================================
        # ⚡ OPTIMIZED UNIFIED ENTITY EXTRACTION (Reduces Latency)
        # =========================================================================
    
        # 1. Base Extraction (Regex/Keyword - FAST)
        school_name = self._extract_school_name(question)
        province = self._extract_province(question)
        region = self._extract_region(question)
        gender = self._extract_gender(question)
        agency = self._extract_agency(question)
        
        # Check if we have what we need?
        # For complex entities (District, Grade, PersonType, Area), try unified LLM call if keywords fail
        
        district = None
        grade = None
        person_type = None
        area_name = None
        
        # 2. Try fast keyword-based extraction first (for Grade/PersonType aliases)
        # Using the "Smart" functions but purely in keyword mode (passing None as client)
        grade = extract_grade_smart(question, None)
        person_type = extract_person_type_smart(question, None)
        
        # 3. If missing key entities, use UNIFIED LLM call (One Call to Rule Them All)
        # We only call LLM if we suspect there are entities we missed via regex
        # Heuristics: if query has words but we found no entities, or specific keywords present
        needs_llm_extraction = False
        
        # Check for keywords suggesting existence of these entities
        has_district_kw = any(k in question for k in ['อำเภอ', 'อ.', 'เขต'])
        has_area_kw = any(k in question for k in ['สพป', 'สพม', 'เขตพื้นที่'])
        has_grade_kw = any(k in question for k in ['ชั้น', 'ป.', 'ม.', 'อนุบาล']) and not grade
        has_person_kw = any(k in question for k in ['ครู', 'อาจารย์', 'บุคลากร']) and not person_type
        
        if has_district_kw or has_area_kw or has_grade_kw or has_person_kw:
            needs_llm_extraction = True
            
        if needs_llm_extraction and self.llm:
            logger.info("⚡ Triggering Unified Entity Extraction (LLM)...")
            extracted = extract_entities_via_llm(question, self.llm)
            
            # Merge if not already found via keyword
            if not district and extracted.get('district'):
                district = extracted['district']
                
            if not area_name and extracted.get('area_name'):
                area_name = extracted['area_name']
                
            if not grade and extracted.get('grade'):
                grade = extracted['grade']
                
            if not person_type and extracted.get('person_type'):
                person_type = extracted['person_type']
                
            if not agency and extracted.get('agency'):
                agency = extracted['agency']

            # Capture INTENT from Unified Extraction
            if extracted.get('intent'):
                logger.info(f"⚡ Unified Extraction predicted intent: {extracted['intent']}")
                extracted_intent = extracted['intent']
            else:
                extracted_intent = None
        else:
             extracted_intent = None
                
        params = {}
        if school_name:
            params["school_name"] = school_name
        elif context and context.get("last_school_name"):
            # 🧠 Context Inject: Use school from memory if not in query
            params["school_name"] = context.get("last_school_name")
            # Also update local var for subsequent logic
            school_name = params["school_name"]
            logger.info(f"🧠 Injected school from context: {params['school_name']}")
            
        if province:
            params["province"] = province
        if region:
            params["region"] = region
        elif context and context.get("last_province") and not school_name and not province:
            # CRITICAL: Only inject province from context if user did NOT specify a new school name
            # If user asks about a specific school, we should search globally, not in memory province
            params["province"] = context.get("last_province")
            province = params["province"]  # Update local var
            logger.info(f"🧠 Injected province from context: {province}")

        if district:
            params["district"] = district
        elif context and context.get("last_district") and not school_name:
            # Don't inject district from context if user specified a new school
            params["district"] = context.get("last_district")
            district = params["district"]  # Update local var
            logger.info(f"🧠 Injected district from context: {district}")

        if agency:
            params["agency"] = agency
        elif context and context.get("last_agency"):
             params["agency"] = context.get("last_agency")
             agency = params["agency"]  # Update local var

        if area_name:
             params["area_name"] = area_name
        if grade:
            params["grade"] = grade
        if person_type:
            params["person_type"] = person_type
            
        # IMPORTANT: Only add gender if user specifically asks for one gender
        # If user asks "ทั้งชายและหญิง" or "รวม" or just "กี่คน", do NOT filter by gender
        asks_for_both = any(kw in question_lower for kw in ['ทั้งชาย', 'ทั้งสองเพศ', 'ทั้งหมด', 'รวม', 'ชายหญิง', 'ทั้งนักเรียน'])
        if gender and not asks_for_both:
            params["gender"] = gender
        
        logger.info(f"🔍 Extracted entities: school={school_name}, province={province}, region={region}, district={district}, agency={agency}, grade={grade}, person_type={person_type}, gender={gender if not asks_for_both else 'N/A (asking for total)'}")
        
        # ============================================================
        # PRIORITY ORDER: More specific queries first!
        # ============================================================
        
        # 0. GENERAL/POLICY QUESTIONS - Let LLM answer directly (no database query)
        # These are education expertise questions, not data lookups
        policy_keywords = [
            'ปรับตัว', 'นโยบาย', 'กลยุทธ์', 'แนวทาง', 'วิธีการ', 'ทำอย่างไร', 'ทำยังไง',
            'ควรจะ', 'ควรทำ', 'แก้ปัญหา', 'พัฒนา', 'ปรับปรุง', 'ปฏิรูป',
            'คิดเห็น', 'เหตุผล', 'ทำไม', 'อธิบาย', 'หมายความว่า',
            'เตรียมตัว', 'รับมือ', 'จัดการ', 'บริหาร', 'วางแผน',
            'แนะนำ', 'เสนอแนะ', 'ข้อเสนอ', 'อนาคต', 'แนวโน้ม',
            'ผลกระทบ', 'ปัจจัย', 'สาเหตุ', 'ประโยชน์', 'ข้อดี', 'ข้อเสีย'
        ]
        # Check if this is a policy/expert question (not a data query)
        is_policy_question = any(kw in question for kw in policy_keywords)
        is_data_query = any(kw in question_lower for kw in ['กี่คน', 'กี่แห่ง', 'กี่โรง', 'จำนวน', 'เท่าไหร่', 'มีกี่', 'รายชื่อ', 'ค้นหา', 'อยู่ที่ไหน', 'พิกัด'])
        
        if is_policy_question and not is_data_query and not school_name:
            logger.info(f"🎓 Detected EDUCATION POLICY question (LLM will answer directly): {question[:50]}...")
            return []  # Empty = no tools needed, LLM responds directly
        
        # 0.5. NATIONAL SUMMARY - ภาพรวมระดับประเทศ
        national_kws = ['ระดับประเทศ', 'ทั้งประเทศ', 'ภาพรวมทั้งประเทศ', 'สรุประดับประเทศ', 'ระดับชาติ', 'ประเทศไทยทั้งหมด']
        is_national = any(k in question for k in national_kws)
        if is_national and not school_name and not province:
            logger.info("🌏 Detected NATIONAL SUMMARY query")
            return [{"name": "get_national_summary", "params": {}}]

        # 1. COMPARISON - เปรียบเทียบ
        # 1. COMPARISON - เปรียบเทียบ
        if any(kw in question_lower for kw in ['เปรียบเทียบ', 'เทียบ', 'ระหว่าง', 'กับ', 'vs']):
            entities = self._extract_comparison_entities(question)
            
            # Determine metric with higher granularity
            if any(kw in question for kw in ['ครู', 'อาจารย์', 'บุคลากร']):
                 metric = "teachers"
            elif any(kw in question for kw in ['โรงเรียน', 'สถานศึกษา']):
                 metric = "schools"
            else:
                 metric = "students"
                 
            return [{"name": "compare", "params": {"entity1": entities[0], "entity2": entities[1], "metric": metric}}]
        
        # 1.5 LOCATION/MAP - แผนที่/ที่อยู่ (Bypass LLM for specific location queries)
        # NOTE: Skip if person_type is present (e.g. "ตำแหน่งราชการ" = personnel position, NOT location)
        location_keywords = ['อยู่ที่ไหน', 'ตั้งอยู่', 'แผนที่', 'พิกัด', 'ที่อยู่']
        is_location_query = any(kw in question for kw in location_keywords)
        if school_name and is_location_query and not person_type:
             logger.info(f"📍 Detected LOCATION query for '{school_name}' -> Direct tool call")
             return [{"name": "get_school_full_details", "params": {"school_name": school_name, "province": province}}]

        # 2. RATIO - อัตราส่วน (BEFORE ครู detection!)
        # BUT skip if ranking keywords present (e.g., "อัตราส่วนสูงที่สุด" → handled by ranking quick-path above)
        ranking_kws_check = ["มากที่สุด", "น้อยที่สุด", "สูงสุด", "ต่ำสุด", "ดีที่สุด", "แย่ที่สุด", "อันดับ"]
        is_ratio_ranking = any(k in question for k in ranking_kws_check)
        if any(kw in question_lower for kw in ['อัตราส่วน', 'ต่อครู', 'ratio', 'นักเรียน:ครู', 'ครู:นักเรียน']) and not is_ratio_ranking:
            return [{"name": "get_ratio", "params": params}]
        
        # 2.5 THRESHOLD FILTER - โรงเรียนที่มีนักเรียน/ครู น้อยกว่า/มากกว่า X คน
        import re
        threshold_patterns = [
            (r'น้อยกว่า\s*(\d+)', 'lt'),
            (r'ต่ำกว่า\s*(\d+)', 'lt'),
            (r'ไม่ถึง\s*(\d+)', 'lt'),
            (r'<\s*(\d+)', 'lt'),
            (r'มากกว่า\s*(\d+)', 'gt'),
            (r'เกิน\s*(\d+)', 'gt'),
            (r'มากกว่า\s*(\d+)', 'gt'),
            (r'>\s*(\d+)', 'gt'),
            (r'ไม่เกิน\s*(\d+)', 'lte'),
            (r'ไม่เกินกว่า\s*(\d+)', 'lte'),
            (r'<=\s*(\d+)', 'lte'),
            (r'อย่างน้อย\s*(\d+)', 'gte'),
            (r'>=\s*(\d+)', 'gte'),
        ]
        
        threshold_value = None
        threshold_operator = None
        for pattern, op in threshold_patterns:
            match = re.search(pattern, question)
            if match:
                threshold_value = int(match.group(1))
                threshold_operator = op
                break
        
        if threshold_value is not None and threshold_operator:
            # Determine metric: students or teachers
            if any(kw in question_lower for kw in ['ครู', 'อาจารย์', 'บุคลากร']):
                metric = "teachers"
            else:
                metric = "students"
            
            # Extract subdistrict if present
            subdistrict = None
            subdistrict_patterns = [r'ตำบล\s*(\S+)', r'แขวง\s*(\S+)']
            for pattern in subdistrict_patterns:
                match = re.search(pattern, question)
                if match:
                    subdistrict = match.group(1)
                    break
            
            filter_params = {
                "metric": metric,
                "operator": threshold_operator,
                "value": threshold_value,
                "limit": 20
            }
            if province:
                filter_params["province"] = province
            if district:
                filter_params["district"] = district
            if subdistrict:
                filter_params["subdistrict"] = subdistrict
                
            logger.info(f"📊 Detected THRESHOLD FILTER query: {metric} {threshold_operator} {threshold_value}, subdistrict={subdistrict}")
            return [{"name": "filter_schools", "params": filter_params}]
        
        # 3. RANKING - มากที่สุด/น้อยที่สุด
        # EXCEPTION: If asking about "which grade" (ชั้นไหน, ระดับไหน) -> Do NOT use ranking (which ranks schools/provinces).
        # Use count_students/get_details instead to show the breakdown.
        is_grade_ranking = any(kw in question_lower for kw in ['ชั้นไหน', 'ระดับไหน', 'ชั้นใด', 'grade'])
        
        if any(kw in question_lower for kw in ['มากที่สุด', 'น้อยที่สุด', 'อันดับ', 'top', 'สูงสุด', 'ต่ำสุด', 'เยอะที่สุด', 'เยอะสุด', 'มากสุด', 'น้อยสุด']) and not is_grade_ranking:
            order = "most" if any(kw in question_lower for kw in ['มากที่สุด', 'สูงสุด', 'top', 'เยอะที่สุด', 'เยอะสุด', 'มากสุด']) else "least"
            # Determine metric from keywords
            if any(kw in question_lower for kw in ['ครู', 'อาจารย์', 'บุคลากร']):
                metric = "teachers"
            elif any(kw in question_lower for kw in ['นักเรียน', 'เด็ก', 'นักศึกษา']):
                metric = "students"
            elif any(kw in question_lower for kw in ['โรงเรียน', 'สถานศึกษา', 'สถาบัน']):
                metric = "schools"
            else:
                metric = "students"  # Default to students

            params = {"metric": metric, "order": order, "limit": 5}
            # If user explicitly asks about provinces (no specific province given), rank provinces by school count
            if metric == "schools" and "จังหวัด" in question_lower and not province:
                params["scope"] = "province"
            elif province:
                params["province"] = province
            return [{"name": "ranking", "params": params}]
        
        # 4. TEACHER COUNT - Should require quantity context
        teacher_kws = ['ครู', 'อาจารย์', 'บุคลากร', 'ข้าราชการ', 'พนักงาน']
        if any(kw in question_lower for kw in teacher_kws):
            # Only trigger if asking for quantity
            logger.info("DEBUG INFER: Matched Teacher keywords")
            quantity_kws = ['กี่คน', 'จำนวน', 'เท่าไหร่', 'เท่าไร', 'มีกี่', 'ทั้งหมด', 'รวม']
            if any(q in question_lower for q in quantity_kws):
                logger.info(f"DEBUG INFER: Matched Quantity context for Teachers. Params: {params}")
                return [{"name": "count_teachers", "params": params}]
            else:
                logger.info("DEBUG INFER: Teacher keywords found but NO Quantity context")
        
        # 5. GRADE DISTRIBUTION - Breakdown by grade (Insert before count_students)
        if any(kw in question_lower for kw in ['แยกตามระดับชั้น', 'แบ่งตามชั้น', 'สรุประดับชั้น', 'ทุกระดับชั้น', 'รายชั้น']):
             # If "student" context
            if any(kw in question_lower for kw in ['นักเรียน', 'เด็ก', 'ผู้เรียน']):
                return [{"name": "get_grade_distribution", "params": params}]

        # 6. STUDENT COUNT - Should require quantity context
        student_kws = ['นักเรียน', 'ผู้เรียน', 'เด็ก', 'นักศึกษา']
        if any(kw in question_lower for kw in student_kws):
            # Only trigger if asking for quantity
            if any(q in question_lower for q in ['กี่คน', 'จำนวน', 'เท่าไหร่', 'เท่าไร', 'มีกี่', 'ทั้งหมด', 'รวม', 'สถิติ']):
                return [{"name": "count_students", "params": params}]
        
        # 6. SCHOOL COUNT - include district and agency!
        if any(kw in question_lower for kw in ['กี่โรงเรียน', 'จำนวนโรงเรียน', 'มีโรงเรียน', 'กี่แห่ง', 'กี่โรง', 'สถานศึกษา']):
            return [{"name": "count_schools", "params": {"province": province, "district": district, "agency": agency}}]
        
        # 7. SCHOOL LIST - include district and agency!
        if any(kw in question_lower for kw in ['รายชื่อ', 'โรงเรียนอะไรบ้าง', 'มีอะไรบ้าง', 'โรงเรียนใดบ้าง']):
            return [{"name": "list_schools", "params": {"province": province, "district": district, "agency": agency, "limit": 10}}]

        # 7.5 SCHOOL DETAILS - Address, Phone, Website, Map
        # BUT: Only trigger if NOT asking about teachers/students (those have dedicated tools!)
        teacher_student_kws = ['ครู', 'อาจารย์', 'นักเรียน', 'ผู้เรียน', 'เด็ก', 'นักศึกษา']
        detail_kws = ['รายละเอียด', 'ที่อยู่', 'เบอร์โทร', 'ติดต่อ', 'เว็บไซต์', 'แผนที่', 'พิกัด', 'รู้จัก', 'ข้อมูลของ']
        if any(kw in question_lower for kw in detail_kws):
            # Check if asking about TEACHERS - use analyze_teacher_distribution instead
            if any(kw in question_lower for kw in ['ครู', 'อาจารย์']):
                logger.info("🔀 Detected 'รายละเอียด + ครู' -> Using analyze_teacher_distribution")
                return [{"name": "analyze_teacher_distribution", "params": params}]
            # Check if asking about STUDENTS - use grade_distribution or count_students
            elif any(kw in question_lower for kw in ['นักเรียน', 'ผู้เรียน', 'เด็ก']):
                logger.info("🔀 Detected 'รายละเอียด + นักเรียน' -> Using get_grade_distribution")
                return [{"name": "get_grade_distribution", "params": params}]
            # Otherwise, it's asking about a specific school
            elif school_name:
                return [{"name": "get_school_full_details", "params": params}]
        
        # 7.6 EDUCATION AREAS - เขตพื้นที่การศึกษา
        if any(kw in question_lower for kw in ['เขตพื้นที่', 'สพป', 'สพม', 'เขตการศึกษา', 'พื้นที่การศึกษา', 'เขต 1', 'เขต 2']):
            return [{"name": "search_education_areas", "params": {"province": province, "district": district}}]
        
        # 7.7 GENDER ANALYSIS - สัดส่วนชายหญิง
        if any(kw in question_lower for kw in ['ชายหญิง', 'สัดส่วนชาย', 'สัดส่วนหญิง', 'เพศชาย', 'เพศหญิง', 'แยกเพศ']):
            return [{"name": "analyze_gender_ratio", "params": {"province": province, "district": district}}]
        
        # 7.8 SYSTEM TYPE - ในระบบ/นอกระบบ
        if any(kw in question_lower for kw in ['ในระบบ', 'นอกระบบ', 'ระบบการศึกษา', 'แยกระบบ']):
            return [{"name": "count_by_system_type", "params": {"province": province}}]
            
        # 7.9 ADVANCED SEARCH (Numeric)
        # If asking for > < amount of students/teachers
        if any(kw in question_lower for kw in ['มากกว่า', 'น้อยกว่า', 'เกิน', 'ถึง', 'ไม่เกิน', 'ตั้งแต่', 'ระหว่าง', 'สูงกว่า', 'ต่ำกว่า']):
            # If keywords suggest students/teachers, imply advanced search
            if any(kw in question_lower for kw in ['นักเรียน', 'คน', 'ผู้เรียน']) or any(kw in question_lower for kw in ['ครู', 'อาจารย์']):
                 # Leave to LLM to extract the exact numbers!
                 logger.info("⚡ Detected numeric criteria - Delegating to LLM for advanced_school_search")
                 return []

        
        # 8. CHECK FOR GENERAL/CASUAL QUERIES - Don't search database!
        # If no education-related keywords found, it's likely a general query
        education_keywords = [
            'โรงเรียน', 'นักเรียน', 'ครู', 'อาจารย์', 'สถานศึกษา', 'การศึกษา',
            'วิทยาลัย','มหาวิทยาลัย', 'สพฐ', 'สังกัด', 'เขต', 'จังหวัด', 'ศพด',
            'กรุงเทพ', 'กระบี่', 'รายละเอียด', 'ที่อยู่', 'ติดต่อ', # Known keywords
            'วัด', 'บ้าน', 'ชุมชน', 'อนุบาล', 'เทศบาล' # Common school prefixes (prevent general fallback)
        ]
        has_education_context = any(kw in question for kw in education_keywords)
        
        # If no education keywords and no entities extracted, treat as GENERAL
        # BUT: Check context first - if user is in a school conversation, don't drop out!
        has_active_context = context.get('last_school_name') is not None if context else False
        
        if not has_education_context and not school_name and not province and not has_active_context:
            logger.info(f"🌐 Detected GENERAL query (no education keywords & no active context): {question}")
            return []  # Empty = no tools needed, LLM will respond directly
        
        # 9. DEFAULT: search schools (only if there's some context)
        if school_name or province or district:
            return [{"name": "search_schools", "params": params}]
        
        # 10. CHECK EXTRACTED INTENT (Unified Extraction Result)
        if extracted_intent:
            logger.info(f"⚡ Using Unified Extraction Intent: {extracted_intent}")
            return [{"name": extracted_intent, "params": params}]

        # 11. NO MATCHED TOOL - Return empty to trigger LLM Tool Selection
        # Crucial for handling typos/synonyms that regex missed but LLM can understand.
        logger.info(f"🌐 No keyword-based tool matched - falling back to LLM Tool Selection: {question}")
        return []
