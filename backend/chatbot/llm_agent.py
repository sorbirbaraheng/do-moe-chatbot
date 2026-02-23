"""
🤖 LLM Agent
The main orchestrator that uses LLM to:
1. Analyze user queries
2. Select appropriate tools
3. Execute tools
4. Generate natural language responses

This replaces the 20+ handler approach with intelligent tool calling.
"""

import json
import logging
import re
import os
from typing import List, Dict, Any, Optional

from .tools import get_tools_prompt, TOOL_SELECTION_PROMPT, RESPONSE_GENERATION_PROMPT, get_tool_by_name
from .tool_executor import ToolExecutor
from .llm import MultiProviderLLM
from .constants import THAI_PROVINCES, PROVINCE_ALIASES, REGIONS
from .entity_extractor import (
    extract_person_type_smart,
    extract_grade_smart,
    extract_area_smart,
    extract_district_smart,
    fetch_valid_values,
    extract_entities_via_llm,
    extract_query_structured_via_llm,
)

logger = logging.getLogger(__name__)


class LLMAgent:
    """
    LLM-powered agent that intelligently selects and executes tools
    to answer education queries comprehensively.
    """
    
    def __init__(self, qdrant_client, llm: MultiProviderLLM):
        self.tool_executor = ToolExecutor(qdrant_client, llm_provider=llm)
        self.llm = llm
        self.tools_prompt = get_tools_prompt()
        self.min_confidence = 0.45
    
    def process_query(self, question: str, context: Dict[str, Any] = None) -> tuple[str, Optional[Dict[str, Any]]]:
        """
        Main entry point: Process a user query using LLM + Tools
        
        Args:
            question: User's question in Thai
            context: Optional context (e.g., session memory)
            
        Returns:
            Tuple[response_text, active_query_info]
        """
        logger.info(f"🤖 LLM Agent processing: {question}")
        
        try:
            # Step 1: Use LLM to analyze query and select tools
            tool_calls = self._select_tools(question, context)
            
            # Ask-back path (no tool execution)
            if tool_calls and tool_calls[0].get("name") == "__ask_back__":
                params = tool_calls[0].get("params", {}) or {}
                msg = params.get("message") or "ขอรายละเอียดเพิ่มอีกนิดได้ไหมครับ"
                pending_tool = params.get("pending_tool")
                # return ask-back message but keep pending tool for follow-up
                return self._format_ask_back(msg), pending_tool

            # Multi-step plan execution
            if tool_calls and tool_calls[0].get("name") == "__multi_step__":
                plan = tool_calls[0].get("params", {}).get("plan") or {}
                response = self._run_multi_step_plan(question, plan)
                return response, None

            # Capture active query (Phase 5 - Follow-up Support)
            active_query = None
            if tool_calls and len(tool_calls) > 0:
                active_query = tool_calls[0]
            
            if not tool_calls:
                logger.warning("⚠️ No tools selected, using fallback")
                return self._fallback_response(question), None
            
            logger.info(f"🔧 Selected {len(tool_calls)} tool(s): {[t['name'] for t in tool_calls]}")
            
            # Step 1.5: Enrich tool params with context (follow-up region/province injection)
            tool_calls = self._enrich_tool_params(question, tool_calls, context)
            
            # Step 2: Execute all selected tools
            results = []
            deterministic_tools = [
                'ranking',
                'count_students',
                'count_teachers',
                'get_school_full_details',
                'get_province_summary',
                'get_grade_distribution',
                'list_schools',
                'get_ratio',
                'advanced_school_search'
            ]
            should_use_deterministic = False
            
            for tool_call in tool_calls:
                name = tool_call["name"]
                if name in deterministic_tools:
                    should_use_deterministic = True
                    
                result = self.tool_executor.execute(
                    name,
                    tool_call.get("params", {})
                )
                results.append(result)
                
            # Step 2.5: self-healing reflection loop for Empty Results
            # If the data returned is empty, we will ask the agent to broaden its search.
            def is_empty_result(res):
                if not isinstance(res, dict): return False
                if res.get("error"): return True
                if "data" in res and not res["data"]: return True
                if "ranking" in res and not res["ranking"]: return True
                if "schools" in res and not res["schools"]: return True
                if "total_schools" in res and res["total_schools"] == 0: return True
                if "total_students" in res and res["total_students"] == 0: return True
                if "total_teachers" in res and res["total_teachers"] == 0: return True
                return False
                
            # If ALL tool results are empty, let's trigger a reflection retry (max 1 retry)
            if results and all(is_empty_result(r) for r in results):
                logger.warning("⚠️ All tool results were empty. Triggering Agentic Reflection Loop...")
                reflection_context = dict(context or {})
                reflection_context["reflection_prompt"] = (
                    "คำค้นหาก่อนหน้านี้ไม่พบข้อมูลในฐานข้อมูลเลย (Empty Result). "
                    "กรุณาลองลดเงื่อนไขที่แคบเกินไป เช่น ตัดชื่ออำเภอ/ตำบลออกเพื่อค้นหาทั่วจังหวัด "
                    "หรือถ้ามีชื่อโรงเรียน ให้ระบุเฉพาะชื่อหลักไม่ต้องใส่คำว่า โรงเรียน หรือลองใช้ tool อื่นที่ขอบเขตกว้างขึ้น"
                )
                # Retry tool selection with reflection context
                retry_tool_calls = self._select_tools(question, reflection_context)
                
                # If LLM decided to change tools/params, execute them again
                if retry_tool_calls and str(retry_tool_calls) != str(tool_calls):
                    logger.info(f"🔄 Retry: Selected new tools: {[t['name'] for t in retry_tool_calls]}")
                    retry_results = []
                    should_use_deterministic = False
                    for tool_call in retry_tool_calls:
                        name = tool_call["name"]
                        if name in deterministic_tools:
                            should_use_deterministic = True
                        result = self.tool_executor.execute(name, tool_call.get("params", {}))
                        retry_results.append(result)
                        
                    # Override original if the retry actually yielded non-empty data
                    if retry_results and not all(is_empty_result(r) for r in retry_results):
                        logger.info("✅ Reflection try succeeded! Replacing empty results with new data.")
                        tool_calls = retry_tool_calls
                        results = retry_results
                    else:
                        logger.warning("❌ Reflection try also yielded empty data. Falling through to original.")
            
            # Step 3: Generate Response
            # Hybrid mode: template for data accuracy → LLM for natural language
            use_deterministic = os.getenv("ENABLE_DETERMINISTIC_RESPONSES", "1") == "1"
            if should_use_deterministic and len(results) == 1 and use_deterministic:
                 logger.info("⚡ Deterministic path → Naturalizing with LLM...")
                 template_text = self._format_fallback_response(results, question)
                 natural_text = self._naturalize_response(template_text, question, results)
                 # Add suggestion chips to deterministic path too
                 suggestions_list = self._get_proactive_suggestions(tool_calls, results)
                 if suggestions_list:
                     import json
                     natural_text += "\n\n<suggestions>" + json.dumps(suggestions_list, ensure_ascii=False) + "</suggestions>"
                 return self._inject_widgets(natural_text, results), active_query
            
            # Step 4: Fallback to LLM for complex queries
            suggestions_list = self._get_proactive_suggestions(tool_calls, results)
            
            # GENERATE RESPONSE
            response = self._generate_response(question, results)
            
            # Embed suggestions as structured tag (frontend renders as clickable chips)
            if suggestions_list:
                import json
                response += "\n\n<suggestions>" + json.dumps(suggestions_list, ensure_ascii=False) + "</suggestions>"

            # Ensure widgets are injected when relevant (if LLM didn't include them)
            response = self._inject_widgets(response, results, question)
            
            return response, active_query
            
        except Exception as e:
            import traceback
            logger.error(f"❌ LLM Agent error: {e}")
            logger.error(f"❌ Full traceback:\n{traceback.format_exc()}")
            return self._error_response(str(e)), None
    
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

    def _try_followup_from_active_query(self, question: str, context: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        active = context.get("last_active_query")
        if not active or not isinstance(active, dict):
            return None

        text = (question or "").strip()
        if not text:
            return None

        # Handle short/medium follow-ups, but ignore long standalone questions
        followup_markers = ["แล้ว", "ล่ะ", "ละ", "ต่อ", "อีก", "เพิ่ม", "ขอ", "รายละเอียด", "เทียบ", "ส่วน", "เฉพาะ"]
        looks_followup = text.startswith(("แล้ว", "งั้น", "ถ้า", "แล้วถ้า")) or any(k in text for k in followup_markers)
        if len(text) > 160 or (len(text) > 40 and not looks_followup):
            return None

        # Detect "latest year" hints
        latest_kws = ["ปีล่าสุด", "ล่าสุด", "ปีนี้", "ปัจจุบัน"]
        is_latest = any(k in text for k in latest_kws)

        # Extract year (Thai/Arabic digits)
        year = self._extract_year_token(text)
        # Extract region/province from short reply
        region = self._extract_region(text)
        province = self._extract_province(text)
        district = self._extract_district(text)
        has_system_followup = any(k in text for k in ["ในระบบ", "นอกระบบ"])
        # Handle "ทั้งภาคใต้/ทั้งภาคเหนือ" style
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

        # If nothing useful found
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

        # Multi-step plan follow-up: inject scope
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

        # Apply year/person_type/scope to last active count tool
        if tool in ["count_teachers", "count_students"]:
            if year:
                params["year"] = year
            else:
                # Latest = no year filter (use most recent data)
                params.pop("year", None)
            if person_type and tool == "count_teachers":
                params["person_type"] = person_type
            # Apply scope if provided in follow-up
            if region and not params.get("region") and not params.get("province"):
                params["region"] = region
            if province and not params.get("province") and not params.get("region"):
                params["province"] = province
            if district and not params.get("district"):
                params["district"] = district
            return [{"name": tool, "params": params}]

        # Apply scope to count_schools / ratio
        if tool in ["count_schools", "get_ratio"]:
            if region and not params.get("region") and not params.get("province"):
                params["region"] = region
            if province and not params.get("province") and not params.get("region"):
                params["province"] = province
            if district and not params.get("district"):
                params["district"] = district
            return [{"name": tool, "params": params}]

        # Threshold follow-up for filter_schools
        if tool == "filter_schools":
            if threshold.get("value") is not None:
                params["value"] = threshold["value"]
            if threshold.get("operator"):
                params["operator"] = threshold["operator"]
            # Switch metric if user mentions it explicitly
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

        # Follow-up from school details: continue within same school context
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

        # If active query is unrelated for follow-up transformation, use standard routing
        return None

    def _extract_threshold_followup(self, text: str) -> Dict[str, Any]:
        """Extract numeric threshold/operator from a short follow-up like 'มากกว่า 1500 คน'."""
        if not text:
            return {"value": None, "operator": None}
        thai_to_arabic = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
        normalized = text.translate(thai_to_arabic)
        import re
        value = None
        operator = None

        # Operators first
        if any(k in normalized for k in [">=", "อย่างน้อย"]):
            operator = "gte"
        elif any(k in normalized for k in ["<=", "ไม่เกิน", "ไม่เกินกว่า"]):
            operator = "lte"
        elif any(k in normalized for k in [">", "มากกว่า", "เกิน", "สูงกว่า", "มากขึ้น"]):
            operator = "gt"
        elif any(k in normalized for k in ["<", "น้อยกว่า", "ต่ำกว่า", "ไม่ถึง"]):
            operator = "lt"

        match = re.search(r'(\d+)', normalized)
        if match:
            try:
                value = int(match.group(1))
            except Exception:
                value = None

        return {"value": value, "operator": operator}

    def _extract_year_token(self, text: str) -> Optional[int]:
        # Convert Thai numerals to Arabic
        thai_to_arabic = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
        normalized = text.translate(thai_to_arabic)

        # Look for 4-digit year
        import re
        match = re.search(r'(\d{4})', normalized)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                return None
        # Look for 2-digit year (assume 25xx)
        match2 = re.search(r'(\d{2})', normalized)
        if match2 and ("ปี" in normalized or "พ.ศ" in normalized or "พศ" in normalized):
            try:
                return 2500 + int(match2.group(1))
            except Exception:
                return None
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

        # Use LLM to narrate the derived result with consistent style
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
        # Fallback by tool type
        tool = res.get("tool")
        if tool == "count_teachers":
            return res.get("total_teachers")
        if tool == "count_students":
            return res.get("total_students")
        if tool == "count_schools":
            return res.get("total_schools")
        return None

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
        follow_kws = ["แล้ว", "ต่อ", "อีก", "เพิ่ม", "ขอรายละเอียด", "รายละเอียด", "พิกัด", "ที่ไหน", "เบอร์ติดต่อ", "ครูกี่", "นักเรียนกี่", "ข้อมูล"]
        starts_followup = q_text.startswith(("แล้ว", "งั้น", "ถ้า", "กรณี", "แล้วถ้า"))
        is_followup = (len(q_text) <= 120 and any(k in q_text for k in follow_kws)) or starts_followup
        
        for tool in tool_calls:
            params = tool.get('params', {})
            
            # Tools that accept school_name (specific school only)
            school_specific_tools = ['get_school_full_details', 'get_grade_distribution']
            # Tools that accept ONLY province (not school_name)
            province_only_tools = ['list_schools', 'advanced_school_search', 'filter_schools']
            aggregation_tools = ['count_students', 'count_teachers', 'count_schools']
            skip_context_tools = ['compare', 'ranking', 'general_chat']
            
            # Context injection for follow-up questions ONLY
            if context and tool['name'] not in skip_context_tools and is_followup:
                # Inject school_name from context ONLY for specific school queries
                # NOT for list/search/filter type queries
                
                # Check for both Memory keys (last_*) and SessionContext keys (current_*)
                ctx_school = context.get('last_school_name') or context.get('current_school')
                ctx_province = context.get('last_province') or context.get('current_province')
                
                if not params.get('school_name') and ctx_school and tool['name'] in school_specific_tools:
                    if ctx_school.replace("โรงเรียน", "").replace(" ", "") in q_norm or is_followup:
                        params['school_name'] = ctx_school
                        logger.info(f"💉 Injected context school_name: {ctx_school}")

                # Inject province from context
                if not params.get('province') and ctx_province:
                    if question_region:
                        # If user asked about a region, don't force a province from context
                        pass
                    else:
                        # If a specific school_name is present, do NOT force province from context
                        # This avoids incorrectly narrowing searches for named schools.
                        if not params.get('school_name'):
                            # Combine school-specific + province-only tools for province injection
                            province_aware_tools = school_specific_tools + province_only_tools + aggregation_tools
                            if isinstance(ctx_province, str) and tool['name'] in province_aware_tools:
                                params['province'] = ctx_province
                                logger.info(f"💉 Injected context province: {ctx_province}")

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
                    from .constants import YEAR_ALIASES, AVAILABLE_YEARS
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
    
    def _extract_school_name(self, question: str) -> Optional[str]:
        """Extract school name from question using patterns - Enhanced for Name+Number"""
        import re
        
        # ============================================================
        # PRIORITY ORDER: Most specific patterns first!
        # ============================================================
        
        # 1. Match "โรงเรียน[Name]" with stop words (zero or more spaces before stop words)
        # Added more stop words to prevent "โรงเรียนกี่แห่ง" -> "กี่แห่ง"
        match = re.search(r'โรงเรียน(.+?)(?=\s*(?:อยู่|มี|กี่|ชั้น|ที่|ใน|จังหวัด|อำเภอ|สังกัด|ครู|นักเรียน|ระดับ|แห่ง|คน|รายชื่อ|เฉพาะ|ตำแหน่ง|หน่อย|ครับ|ค่ะ|นะ|บ้าง|$))', question)
        if match:
            school = match.group(1).strip()
            # Blacklist common false positives
            bad_tokens = [
                'การสอน', 'การเรียน', 'การศึกษา', 'อะไรบ้าง', 'อย่างไร', 'ไหม',
                'ที่มี', 'ซึ่ง', 'ทั้งหมด', 'กี่', 'ใด', 'นี้', 'นั้น', 'โน้น',
                'สพฐ', 'สช', 'อปท', 'ตชด', 'กทม', 'เอกชน', 'ในระบบ', 'นอกระบบ',
                'นักเรียน', 'ครู', 'บุคลากร', 'คน', 'แห่ง', 'มากกว่า', 'น้อยกว่า',
                'ไม่เกิน', 'ต่ำกว่า', 'อย่างน้อย', 'ที่นักเรียน', 'ที่ครู',
                # Ranking/size/comparison stop words
                'มาก', 'น้อย', 'ขนาด', 'ขนาดเล็ก', 'ขนาดใหญ่', 'ขนาดกลาง',
                'ดีที่สุด', 'แย่ที่สุด', 'มากที่สุด', 'น้อยที่สุด', 'อันดับ',
                'ชายแดน', 'ใกล้', 'ไกล', 'ทุก', 'หมด', 'ทั้ง', 'แต่ละ', 'รวม',
                'ไหน', 'อะไร', 'เท่าไหร่', 'เท่าไร',
            ]
            if any(x in school for x in bad_tokens):
                logger.info(f"🏫 Ignoring false positive school name: '{school}'")
                return None
                
            if len(school) > 2:
                logger.info(f"🏫 Extracted school (prefix pattern): '{school}'")
                return school
        
        # 2. Match "Thai Name + Number" pattern (e.g., "ราชประชานุเคราะห์ 40")
        # This handles names WITHOUT "โรงเรียน" prefix
        match_num = re.search(r'([ก-๙]+\s+\d+)', question)
        if match_num:
            candidate = match_num.group(1).strip()
            # Filter out grade patterns like "ม 2", "ป 6"
            bad_num_tokens = ['นักเรียน', 'ครู', 'คน', 'แห่ง', 'มากกว่า', 'น้อยกว่า', 'ไม่เกิน', 'ต่ำกว่า', 'อย่างน้อย']
            if candidate.startswith("ที่") or any(x in candidate for x in bad_num_tokens):
                logger.info(f"🏫 Ignoring false positive school name (num pattern): '{candidate}'")
                return None
            if len(candidate) > 5 and not re.match(r'^[มป]\s*\d', candidate):
                logger.info(f"🏫 Extracted school (name+number pattern): '{candidate}'")
                return candidate
        
        # 2.5 NEW: Match "Thai Name + จังหวัด" pattern (e.g., "พัฒนาวิทยา จังหวัดยะลา")
        # This catches school names BEFORE a province specification
        match_before_province = re.search(r'^([ก-๙a-zA-Z]+)(?:\s+(?:จังหวัด|จ\.))', question)
        if match_before_province:
            candidate = match_before_province.group(1).strip()
            # Filter out province names being confused as school names
            from .thai_provinces import THAI_PROVINCES
            if candidate not in THAI_PROVINCES and len(candidate) > 2:
                logger.info(f"🏫 Extracted school (before-province pattern): '{candidate}'")
                return candidate
        
        # 3. NEW: Detect famous school name keywords (without prefix)
        # These are well-known school names that people often search without "โรงเรียน"
        famous_school_keywords = [
            'สวนกุหลาบ', 'เตรียมอุดม', 'บดินทร', 'เบญจมราชูทิศ', 'เบญจมราชรังสฤษฎิ์',
            'หอวัง', 'สาธิต', 'มหิดลวิทยานุสรณ์', 'กรุงเทพคริสเตียน', 'อัสสัมชัญ',
            'เซนต์คาเบรียล', 'วชิราวุธ', 'ราชินี', 'สตรีวิทยา', 'ศรีอยุธยา',
            'ปัญญาภิวัฒน์', 'ดรุณสิกขาลัย', 'สารสาสน์', 'ราชวินิต', 'พระตำหนัก',
            'นวมินทราชินูทิศ', 'ราชประชานุเคราะห์', 'จุฬาภรณ', 'กำเนิดวิทย์',
            'วิทยาลัยเทคนิค', 'วิทยาลัยอาชีวศึกษา', 'วิทยาลัยการอาชีพ',
        ]
        
        for kw in famous_school_keywords:
            if kw in question:
                logger.info(f"🏫 Extracted school (famous keyword): '{kw}'")
                return kw
        
        # 3.5 NEW: Institution prefix patterns (ศูนย์, สถาบัน, กศน, etc.)
        # These are education institutions that don't start with "โรงเรียน"
        institution_stop = r'(?=\s*(?:มี|กี่|ที่|ใน|ครู|นักเรียน|หน่อย|ครับ|ค่ะ|นะ|บ้าง|$))'
        institution_patterns = [
            r'(ศูนย์ส่งเสริมการเรียนรู้[ก-๙a-zA-Z\s]+?)' + institution_stop,
            r'(ศูนย์การเรียนรู้[ก-๙a-zA-Z\s]+?)' + institution_stop,
            r'(ศูนย์การศึกษา[ก-๙a-zA-Z\s]+?)' + institution_stop,
            r'(ศูนย์กศน[ก-๙a-zA-Z\s\.]+?)' + institution_stop,
            r'(กศน\.?\s*[ก-๙a-zA-Z\s]+?)' + institution_stop,
            r'(สถาบัน[ก-๙a-zA-Z\s]+?)' + institution_stop,
        ]
        for pattern in institution_patterns:
            match = re.search(pattern, question)
            if match:
                institution = match.group(1).strip()
                if len(institution) > 5:
                    logger.info(f"🏫 Extracted school (institution pattern): '{institution}'")
                    return institution
        
        # 4. Fallback: Simple prefix patterns
        # Use lookahead to stop at common keywords
        stop_words = r'(?=\s*(?:มี|กี่|ชั้น|ที่|ใน|จังหวัด|อำเภอ|สังกัด|ครู|นักเรียน|ระดับ|หน่อย|ครับ|ค่ะ|นะ|บ้าง|$))'
        patterns = [
            r'โรงเรียน([ก-๙a-zA-Z\s]+)' + stop_words,
            r'รร\.([ก-๙a-zA-Z\s]+)' + stop_words,
            r'รร\s+([ก-๙a-zA-Z\s]+)' + stop_words,
            r'วิทยาลัย([ก-๙a-zA-Z\s]+)' + stop_words,
            # Strict Technical College pattern: Must start with วิทยาลัยเทคนิค or just เทคนิค followed by province/name
            # Prevent matching "เทคนิคการสอน" (Teaching Technique)
            r'(?:วิทยาลัย)?เทคนิค([ก-๙a-zA-Z\s]+?)' + stop_words,
            # New Prefixes for generic school names (Wat, Ban, Chumchon, etc.)
            r'(?:วัด|บ้าน|ชุมชน|อนุบาล|เทศบาล)\s*([ก-๙a-zA-Z0-9\s]+)' + stop_words,
        ]
        
        for pattern in patterns:
            match = re.search(pattern, question)
            if match:
                school = match.group(1).strip()
                # Remove trailing keywords
                for suffix in ['มี', 'กี่', 'ชั้น', 'นักเรียน', 'ครู', 'แห่ง', 'คน']:
                    if school.endswith(suffix):
                        school = school[:-len(suffix)].strip()
                
                # Check length and blacklisted words
                if len(school) > 2 and school not in ['กี่แห่ง', 'กี่คน', 'อะไรบ้าง', 'อย่างไร', 'ทั้งหมด']:
                    logger.info(f"🏫 Extracted school (fallback pattern): '{school}'")
                    return school
        
        return None
    
    def _extract_province(self, question: str) -> Optional[str]:
        """Extract province name from question using THAI_PROVINCES constant"""
        placeholder_words = {"ไหน", "ใด", "อะไร", "ไหนบ้าง", "ทั้งหมด", "เท่าไหร่", "กี่แห่ง", "กี่โรง"}
        
        # 1. Check aliases first (e.g. กทม -> กรุงเทพมหานคร)
        for alias, full_name in PROVINCE_ALIASES.items():
            if alias in question:
                return full_name
                
        # 2. Check full province names (Prioritize longer names to avoid partial matches)
        # Sort by length desc (e.g. ensure "นครศรีธรรมราช" matches before "นคร...")
        sorted_provinces = sorted(THAI_PROVINCES, key=len, reverse=True)
        
        for p in sorted_provinces:
            if p in question:
                if p == "เลย" and "เลย" in question:
                     # "เลย" is tricky (province vs "at all"). Only match if preceded by "จังหวัด" or "เมือง"
                     if "จังหวัดเลย" in question or "เมืองเลย" in question:
                         return p
                     continue
                return p
                
        # 3. Fallback: Pattern "จังหวัด[ชื่อ]"
        import re
        pattern = r'จังหวัด\s*([ก-๙]+?)(?=มี|มีกี่|อยู่|ที่|ใน|$|\s)'
        match = re.search(pattern, question)
        if match:
            province = match.group(1).strip()
            if province in placeholder_words or province.startswith(("ไหน", "ใด", "อะไร")):
                return None
            if province in THAI_PROVINCES:
                return province
        
        return None

    def _extract_region(self, question: str) -> Optional[str]:
        """Extract region (ภาค) name from question"""
        # Common aliases
        region_aliases = {
            "อีสาน": "ภาคตะวันออกเฉียงเหนือ",
            "ภาคอีสาน": "ภาคตะวันออกเฉียงเหนือ",
            "ตะวันออกเฉียงเหนือ": "ภาคตะวันออกเฉียงเหนือ",
        }
        for alias, full in region_aliases.items():
            if alias in question:
                return full

        # Direct match on configured regions
        for region in REGIONS.keys():
            if region in question:
                return region

        return None
    
    def _extract_gender(self, question: str) -> Optional[str]:
        """Extract gender from question"""
        # Check for female keywords
        female_keywords = ['เพศหญิง', 'ผู้หญิง', 'หญิง', 'สตรี']
        for kw in female_keywords:
            if kw in question:
                return 'หญิง'
        
        # Check for male keywords
        male_keywords = ['เพศชาย', 'ผู้ชาย', 'ชาย']
        for kw in male_keywords:
            if kw in question:
                return 'ชาย'
        
        return None
    
    def _extract_grade(self, question: str) -> Optional[str]:
        """Extract grade level from question (ม.2, ป.6, etc.)"""
        import re
        
        # Pattern mappings: regex -> normalized grade
        grade_patterns = [
            (r'ม\.?\s*(\d)', 'ม.'),           # ม.2, ม2, ม 2
            (r'มัธยม\s*(\d)', 'ม.'),           # มัธยม2, มัธยม 2
            (r'ป\.?\s*(\d)', 'ป.'),             # ป.6, ป6, ป 6
            (r'ประถม\s*(\d)', 'ป.'),           # ประถม6, ประถม 6
            (r'ชั้น\s*ม\.?\s*(\d)', 'ม.'),      # ชั้นม.2, ชั้น ม 2
            (r'ชั้น\s*ป\.?\s*(\d)', 'ป.'),      # ชั้นป.6, ชั้น ป 6
            (r'อนุบาล\s*(\d)?', 'อนุบาล'),     # อนุบาล, อนุบาล1
            (r'ปวช\.?\s*(\d)', 'ปวช.'),        # ปวช.1
            (r'ปวส\.?\s*(\d)', 'ปวส.'),        # ปวส.1
            (r'ประกาศนียบัตรวิชาชีพชั้นสูง\s*ปีที่\s*(\d)', 'ปวส.'), # ประกาศนียบัตรวิชาชีพชั้นสูงปีที่ 1
            (r'ประกาศนียบัตรวิชาชีพ\s*ปีที่\s*(\d)', 'ปวช.'),       # ประกาศนียบัตรวิชาชีพปีที่ 1
        ]
        
        for pattern, prefix in grade_patterns:
            match = re.search(pattern, question, re.IGNORECASE)
            if match:
                if match.groups() and match.group(1):
                    grade = f"{prefix}{match.group(1)}"
                else:
                    grade = prefix
                logger.info(f"📚 Extracted grade: '{grade}'")
                return grade
        
        return None
    
    def _extract_agency(self, question: str) -> Optional[str]:
        """Extract agency/สังกัด from question"""
        question_lower = question.lower()
        
        # Agency mappings (abbreviation -> return value)
        agency_mappings = [
            (['สพฐ', 'สพฐ.'], 'สพฐ'),
            (['สช', 'สช.', 'เอกชน'], 'สช'),
            (['อปท', 'อปท.', 'ท้องถิ่น'], 'อปท'),
            (['กทม', 'กทม.'], 'กทม'),
            (['สอศ', 'สอศ.', 'อาชีวะ', 'อาชีวศึกษา'], 'สอศ'),
            (['ตชด', 'ตชด.'], 'ตชด'),
        ]
        
        for keywords, agency in agency_mappings:
            for kw in keywords:
                if kw in question_lower:
                    return agency
        
        return None
    
    def _extract_person_type(self, question: str) -> Optional[str]:
        """Extract teacher/staff type from question (ข้าราชการครู, พนักงานราชการ, etc.)"""
        
        # Keyword aliases mapping (user terms → database values)
        # Format: (list of user keywords, actual database value)
        keyword_mappings = [
            (['ตำแหน่งราชการ', 'ข้าราชการครู', 'สถานะราชการ'], 'ข้าราชการครู'),
            (['พนักงานราชการ'], 'พนักงานราชการ'),
            (['ครูอัตราจ้าง', 'อัตราจ้าง'], 'ครูอัตราจ้าง'),
            (['ลูกจ้างประจำ'], 'ลูกจ้างประจำ'),
            (['ลูกจ้างชั่วคราว'], 'ลูกจ้างชั่วคราว'),
            (['ผู้อำนวยการ', 'ผอ.', 'ผอ'], 'ผู้อำนวยการ'),
            (['รองผู้อำนวยการ', 'รอง ผอ.', 'รอง ผอ'], 'รองผู้อำนวยการ'),
            (['ครูพิเศษ'], 'ครูพิเศษ'),
            (['วิทยากร'], 'วิทยากร'),
        ]
        
        for user_keywords, db_value in keyword_mappings:
            for kw in user_keywords:
                if kw in question:
                    logger.info(f"👔 Extracted person_type: '{kw}' → '{db_value}'")
                    return db_value
        
        # Fallback: direct match for any person_type in question
        person_types = [
            "ข้าราชการครู", "ข้าราชการ", "พนักงานราชการ",
            "ครูอัตราจ้าง", "ลูกจ้างประจำ", "ลูกจ้างชั่วคราว",
        ]
        
        for pt in person_types:
            if pt in question:
                logger.info(f"👔 Extracted person_type (direct): '{pt}'")
                return pt
        
        return None
    
    def _extract_district(self, question: str) -> Optional[str]:
        """Extract district name from question (Bangkok + general 'อำเภอ/เขต')"""
        import re
        placeholder_words = {"ไหน", "ใด", "อะไร", "ไหนบ้าง", "ทั้งหมด", "เท่าไหร่", "กี่แห่ง", "กี่โรง"}

        # General patterns: อำเภอ/เขต
        # e.g. "อำเภอกะพ้อ", "อำเภอเมืองสุราษฎร์ธานี", "เขตบางรัก"
        match = re.search(r'อำเภอ\s*(เมือง[ก-๙]+?)(?=มี|มีกี่|อยู่|ที่|ใน|$|\s)', question)
        if match:
            return match.group(1).strip()

        match = re.search(r'อำเภอ\s*([ก-๙]+?)(?=มี|มีกี่|อยู่|ที่|ใน|$|\s)', question)
        if match:
            district = match.group(1).strip()
            if district in placeholder_words or district.startswith(("ไหน", "ใด", "อะไร")):
                return None
            if district == "เมือง":
                # If province exists, return เมือง{จังหวัด}
                prov = self._extract_province(question)
                if prov:
                    return f"เมือง{prov}"
            return district

        match = re.search(r'เขต\s*([ก-๙]+?)(?=มี|มีกี่|อยู่|ที่|ใน|$|\s)', question)
        if match:
            district = match.group(1).strip()
            if district in placeholder_words or district.startswith(("ไหน", "ใด", "อะไร")):
                return None
            return district
        
        # Bangkok districts list
        bangkok_districts = [
            'ดุสิต', 'พระนคร', 'ป้อมปราบศัตรูพ่าย', 'สัมพันธวงศ์', 'บางรัก', 
            'ปทุมวัน', 'สาทร', 'บางคอแหลม', 'ยานนาวา', 'คลองเตย', 'วัฒนา',
            'พระโขนง', 'บางนา', 'สวนหลวง', 'ประเวศ', 'คันนายาว', 'สะพานสูง',
            'ลาดกระบัง', 'หนองจอก', 'มีนบุรี', 'คลองสามวา', 'ลาดพร้าว', 
            'บางกะปิ', 'วังทองหลาง', 'บึงกุ่ม', 'ห้วยขวาง', 'ดินแดง', 
            'พญาไท', 'ราชเทวี', 'จตุจักร', 'หลักสี่', 'ดอนเมือง', 
            'สายไหม', 'บางเขน', 'บางซื่อ', 'จอมทอง', 'บางขุนเทียน',
            'ราษฎร์บูรณะ', 'ทุ่งครุ', 'บางบอน', 'ภาษีเจริญ', 'บางแค', 
            'หนองแขม', 'ตลิ่งชัน', 'บางพลัด', 'บางกอกน้อย', 'บางกอกใหญ่',
            'ธนบุรี', 'คลองสาน', 'ทวีวัฒนา'
        ]
        
        # Check for pattern: เขต[ชื่อ]
        pattern = r'เขต([ก-๙]+)'
        match = re.search(pattern, question)
        if match:
            district = match.group(1).strip()
            # Verify it's a valid Bangkok district
            for d in bangkok_districts:
                if d in district or district in d:
                    return d
            return district  # Return extracted even if not in list
        
        # Check for direct district name mention
        for d in bangkok_districts:
            if d in question:
                return d
        
        return None
    
    def _extract_comparison_entities(self, question: str) -> tuple:
        """Extract two entities from comparison question"""
        import re
        
        # Pattern: เปรียบเทียบ...ระหว่าง X กับ Y
        # Pattern: เปรียบเทียบ...ระหว่าง X กับ Y (Support "เทียบ" alias)
        pattern = r'(?:ระหว่าง|เปรียบเทียบ|เทียบ)\s*(?:โรงเรียน)?([ก-๙a-zA-Z\s]+?)(?:กับ|และ)\s*(?:โรงเรียน)?([ก-๙a-zA-Z\s]+?)(?:$|\s)'
        match = re.search(pattern, question)
        return ("", "")
    
    def _get_proactive_suggestions(self, tool_calls: List[Dict], results: List[Dict]) -> List[str]:
        """
        Generate proactive follow-up suggestions based on tool results.
        Returns a list of suggestion strings for frontend to render as clickable chips.
        """
        suggestions = []
        
        for tool_call, result in zip(tool_calls, results):
            name = tool_call.get("name")
            params = tool_call.get("params", {})
            
            # Scenario 1: User asked for school details
            if name == "get_school_full_details" or (name == "search_schools" and result.get("total_count", 0) == 1):
                school_name = params.get("school_name") or "โรงเรียนนี้"
                suggestions.append(f"เปรียบเทียบจำนวนนักเรียนของ {school_name} กับโรงเรียนใกล้เคียง")
                suggestions.append(f"ดูอัตราส่วนครูต่อนักเรียนของ {school_name}")
                suggestions.append(f"ดูจำนวนนักเรียนแยกตามระดับชั้น (ชาย/หญิง)")

            # Scenario 2: User asked for student count (School level)
            elif name == "count_students" and params.get("school_name"):
                suggestions.append("ดูจำนวนครูเพื่อหาอัตราส่วน")
                suggestions.append("ดูข้อมูลที่ตั้งและรายละเอียดโรงเรียนเพิ่มเติม")

            # Scenario 3: User asked for student count (Province level)
            elif name == "count_students" and params.get("province"):
                prov = params.get("province")
                suggestions.append(f"จัดอันดับ 5 โรงเรียนที่มีนักเรียนมากที่สุดใน{prov}")
                suggestions.append(f"ดูจำนวนโรงเรียนทั้งหมดใน{prov}")
            
            # Scenario 4: Ranking
            elif name == "ranking":
                suggestions.append("ดูรายละเอียดของโรงเรียนอันดับ 1")
                suggestions.append("เปรียบเทียบโรงเรียนอันดับ 1 กับอันดับ 2")

            # Scenario 5: Province summary
            elif name == "get_province_summary":
                prov = params.get("province") or "จังหวัดนี้"
                suggestions.append(f"จัดอันดับโรงเรียนที่มีนักเรียนมากที่สุดใน{prov}")
                suggestions.append(f"อัตราส่วนครูต่อนักเรียนของ{prov}")
                suggestions.append(f"แยกจำนวนนักเรียนตามอำเภอใน{prov}")

            # Scenario 6: Teacher count
            elif name == "count_teachers":
                if params.get("school_name"):
                    suggestions.append(f"ดูจำนวนนักเรียนของ {params['school_name']}")
                    suggestions.append(f"ดูอัตราส่วนครูต่อนักเรียนของ {params['school_name']}")
                elif params.get("province"):
                    suggestions.append(f"แยกตามประเภทบุคลากรใน{params['province']}")
                    suggestions.append(f"จัดอันดับโรงเรียนที่มีครูมากที่สุดใน{params['province']}")

            # Scenario 7: Count schools
            elif name == "count_schools":
                prov = params.get("province")
                if prov:
                    suggestions.append(f"จัดอันดับโรงเรียนที่มีนักเรียนมากที่สุดใน{prov}")
                    suggestions.append(f"อัตราส่วนครูต่อนักเรียนของ{prov}")
                    suggestions.append(f"จำนวนครูทั้งหมดใน{prov}")

            # Scenario 8: Search/List schools (multi-result)
            elif name in ("search_schools", "list_schools", "advanced_school_search"):
                prov = params.get("province")
                if prov:
                    suggestions.append(f"จัดอันดับโรงเรียนที่มีนักเรียนมากที่สุดใน{prov}")
                    suggestions.append(f"จำนวนนักเรียนทั้งหมดใน{prov}")
                    suggestions.append(f"อัตราส่วนครูต่อนักเรียนของ{prov}")
                else:
                    suggestions.append("ดูรายละเอียดเพิ่มเติมของโรงเรียนลำดับแรก")
                    suggestions.append("จัดอันดับโรงเรียนที่มีนักเรียนมากที่สุด")

            # Scenario 9: Get ratio
            elif name == "get_ratio":
                school_name = params.get("school_name")
                prov = params.get("province")
                if school_name:
                    suggestions.append(f"ดูจำนวนนักเรียนแยกตามระดับชั้นของ {school_name}")
                    suggestions.append(f"ดูรายละเอียดเพิ่มเติมของ {school_name}")
                elif prov:
                    suggestions.append(f"จัดอันดับโรงเรียนที่มีอัตราส่วนครูต่อนักเรียนดีที่สุดใน{prov}")
                    suggestions.append(f"จำนวนครูทั้งหมดใน{prov}")

            # Scenario 10: Grade distribution
            elif name == "get_grade_distribution":
                school_name = params.get("school_name")
                if school_name:
                    suggestions.append(f"ดูอัตราส่วนครูต่อนักเรียนของ {school_name}")
                    suggestions.append(f"เปรียบเทียบ {school_name} กับโรงเรียนใกล้เคียง")

        if not suggestions:
            return []
            
        return suggestions[:3]

    def _generate_response(self, question: str, results: List[Dict], suggestions_str: str = "") -> str:
        """Use LLM to generate natural language response from tool results"""
        # Convert results to JSON string (optionally strip year/source when not asked)
        import json
        sanitized_results = results
        if not self._question_mentions_year(question):
            sanitized_results = self._strip_fields(results, {"year", "source"})
        data_str = json.dumps(sanitized_results, ensure_ascii=False, indent=2)
        
        # Construct the dynamic prompt
        system_instruction = RESPONSE_GENERATION_PROMPT
        
        if suggestions_str:
            # Inject PROACTIVE INSTRUCTION
            # We add a specific instruction to the prompt telling AI to use these suggestions naturally
            suggestions_instruction = f"""
            
---
**⚡ EXECUTIVE ASSISTANT MODE ACTIVE:**
The system has identified these potential follow-up actions for the user:
{suggestions_str}

**YOUR TASK:**
After answering the main question, please **NATURALLY** suggest 1-2 of these actions to the user.
- Do NOT just copy-paste the list.
- Weave it into your closing sentence.
- Example: "If you're interested, I can also compare this school with..."
- Make it sound helpful, not robotic.
---
"""
            system_instruction += suggestions_instruction

        context_vars = {
            "data": data_str,
            "question": question
        }

        # Helper: Check if this is a general chat fallback
        is_general_chat = any(r.get("type") == "general_knowledge" or r.get("tool") == "general_chat" for r in results)
        
        if is_general_chat:
            logger.info("🗣️ Detected General Chat - using conversational prompt")
            prompt = f"""คุณคือ "น้องดีโอ" (DO AI) ผู้ช่วย AI อารมณ์ดีจากกระทรวงศึกษาธิการ
            
            **คำถามจากผู้ใช้:** "{question}"
            
            **คำสั่ง:**
            - ตอบคำถามนี้โดยใช้ความรู้ทั่วไปของคุณ (เพราะไม่มีข้อมูลใน Database โรงเรียน)
            - ถ้าผู้ใช้ทักทาย/ขอบคุณ/พูดคุยทั่วไป ให้ตอบสั้น ๆ สุภาพ แล้วชวนถามเรื่องการศึกษา 1 ประโยค
            - **เน้นคำสำคัญ:** ให้ใช้ **ตัวหนา (Bold)** กับคำสำคัญ, ชื่อวิชา, หรือประเด็นหลัก เพื่อให้อ่านง่าย
            - ถ้าเป็นเรื่องขั้นตอน, ระเบียบ, หรือความรู้ทั่วไป ให้ตอบให้เป็นประโยชน์ที่สุด
            - ตอบสุภาพ เป็นกันเอง แบบงานบริการ ความยาวประมาณ 3–5 ประโยค (ลงท้ายด้วย "ครับ" พอดี ๆ)
            - ห้ามใช้คำว่า "ค่ะ"
            - ถ้าผู้ใช้ไม่ได้ถามเรื่องปี/ช่วงเวลา **ห้ามพูดถึงปี**
            - ห้ามบอกว่า "ไม่มีข้อมูล" หรือ "ไม่พบข้อมูล" ให้พยายามตอบเท่าที่ทำได้
            """
        else:
            # Standard Data Response
            data_str = json.dumps(sanitized_results, ensure_ascii=False, indent=2)
            prompt = system_instruction.format(
                data=data_str,
                question=question
            )
        
        # Optimize: Try ONCE. MultiProviderLLM handles key rotation/provider fallback internally.
        # If it fails there, it means ALL keys are exhausted. Retrying immediately here won't help.
        try:
            logger.info(f"🤖 Generating response (hybrid pro)...")
            response = self.llm.generate_content(prompt, timeout=45) # Single generous timeout
            
            if response and response.text:
                logger.info(f"✅ LLM response generated successfully")
                final_text = response.text.strip()
                return self._inject_widgets(final_text, results, question)
                
        except Exception as e:
            logger.warning(f"⚠️ Response generation failed: {e}")
            
        logger.error(f"❌ Fallback to deterministic (Quota exhausted)")
        # Fallback: format data nicely
        fallback_text = self._format_fallback_response(results, question)
        return self._inject_widgets(fallback_text, results, question)

    def _naturalize_response(self, template_text: str, question: str, results: list) -> str:
        """
        Post-process a template response with LLM to make it sound natural.
        Preserves <chart>, <map>, and other UI tags.
        Falls back to template if LLM fails.
        """
        import re as _re
        import json as _json
        
        if not template_text or not template_text.strip():
            return template_text
        
        # 1. Extract UI widget tags (<chart>...</chart>, <map>...</map>)
        widget_tags = []
        tag_pattern = _re.compile(r'(<(?:chart|map)>.*?</(?:chart|map)>)', _re.DOTALL)
        for match in tag_pattern.finditer(template_text):
            widget_tags.append(match.group(1))
        
        # Strip widget tags from text for LLM processing
        text_only = tag_pattern.sub('', template_text).strip()
        
        if not text_only:
            return template_text
        
        # 2. Build prompt for LLM rewriting
        prompt = f"""คุณคือ "น้องดีโอ" (DO AI) ผู้ช่วยข้อมูลการศึกษาจากกระทรวงศึกษาธิการ

**งานของคุณ:** เขียนคำตอบใหม่จากข้อมูลด้านล่าง ให้อ่านเป็นธรรมชาติ สุภาพ เป็นกันเอง

**กฎเหล็ก:**
- ตัวเลขทุกตัวต้องตรงกับข้อมูลที่ให้ 100% ห้ามแต่งเพิ่ม ห้ามปัดเศษ
- ใช้ "ครับ" ลงท้าย พอดีๆ ไม่ย้ำบ่อย
- ห้ามขึ้นต้นด้วย "จากข้อมูล..." "จากฐานข้อมูล..." "จากการตรวจสอบ..."
- ห้ามพูดถึงปีการศึกษา เว้นแต่ผู้ใช้ถามเรื่องปี
- ถ้ามีข้อมูลจัดอันดับ ให้ใช้ Markdown table แสดง
- ถ้ามีข้อมูลเยอะ ให้สรุปภาพรวมสั้นๆ ก่อน แล้วค่อยแสดงรายละเอียด
- ความยาว 3-6 ประโยค (ไม่นับตาราง)
- อีโมจิ 0-1 ตัวต่อคำตอบ
- ห้ามบอกว่าคุณกำลัง "เขียนใหม่" หรือ "ปรับปรุง"
- ห้ามเพิ่มข้อเสนอแนะ/คำถามต่อยอด เช่น "เรื่องน่ารู้เพิ่มเติม" หรือ "💡" (ระบบจัดการแยกแล้ว)

**คำถามผู้ใช้:** "{question}"

**ข้อมูลที่ต้องใช้ (ตัวเลขทุกตัวต้องตรง):**
{text_only}

**เขียนคำตอบใหม่:**"""
        
        try:
            logger.info("🎨 Naturalizing template response with LLM...")
            response = self.llm.generate_content(prompt, timeout=20)
            
            if response and response.text and len(response.text.strip()) > 20:
                natural = response.text.strip()
                logger.info(f"✅ Naturalized response ({len(template_text)} → {len(natural)} chars)")
                
                # 3. Re-append widget tags
                if widget_tags:
                    natural += "\n\n" + "\n".join(widget_tags)
                
                return natural
            else:
                logger.warning("⚠️ LLM returned empty/short response, using template")
                
        except Exception as e:
            logger.warning(f"⚠️ Naturalization failed ({e}), using template")
        
        # Fallback: return original template
        return template_text

    def _question_mentions_year(self, question: str) -> bool:
        if not question:
            return False
        q = question.lower()
        year_markers = ["ปี", "ปีการศึกษา", "พ.ศ", "ค.ศ", "20", "25"]
        if any(m in q for m in year_markers):
            return True
        return False

    def _strip_fields(self, obj: Any, keys_to_strip: set) -> Any:
        """Recursively remove keys from dict/list to avoid unnecessary mentions (e.g., year)."""
        if isinstance(obj, dict):
            return {k: self._strip_fields(v, keys_to_strip) for k, v in obj.items() if k not in keys_to_strip}
        if isinstance(obj, list):
            return [self._strip_fields(v, keys_to_strip) for v in obj]
        return obj

    def _generate_map_json(self, schools: List[Dict]) -> str:
        """Helper to generate Map Widget JSON for single or multiple schools"""
        import json
        
        if not schools:
            return ""
            
        # Primary marker (use the first one as center/main)
        primary = schools[0]
        
        # Build Address
        parts = []
        if primary.get("subdistrict"): parts.append(str(primary.get("subdistrict")))
        if primary.get("district"): parts.append(str(primary.get("district")))
        if primary.get("province"): parts.append(str(primary.get("province")))
        if primary.get("postcode"): parts.append(str(primary.get("postcode")))
        address = " ".join(parts)

        data = {
            "latitude": float(primary.get("lat", 0)),
            "longitude": float(primary.get("lon", 0)),
            "schoolName": primary.get("name", ""),
            "address": address
        }

        # If multiple schools, add 'markers' field
        if len(schools) > 1:
            markers = []
            for s in schools:
                markers.append({
                    "lat": float(s.get("lat", 0)),
                    "lng": float(s.get("lon", 0)),
                    "title": s.get("name", "")
                })
            data["markers"] = markers
            
        return json.dumps(data, ensure_ascii=False)

    def _inject_widgets(self, text: str, results: List[Dict], question: str = "") -> str:
        """Inject UI widgets (Map, Chart, etc.) based on data"""
        try:
            import json
            
            # Check for explicit user request for a chart
            chart_keywords = ['กราฟ', 'แผนภูมิ', 'chart', 'graph', 'visual', 'trend', 'แนวโน้ม']
            is_explicit_chart_req = any(k in question.lower() for k in chart_keywords)

            # Loop through results to find widget opportunities
            for res in results:
                tool = res.get("tool")
                
                # ============================================
                # LLM-DRIVEN FORMAT SELECTION (NEW APPROACH)
                # ============================================
                # Map and Chart widgets are now handled by LLM via RESPONSE_GENERATION_PROMPT
                # The LLM decides whether to include <map> or <chart> based on context
                # Keeping this code as fallback (commented out) if LLM fails to include widgets
                
                # FALLBACK: Map Widget Injection (only if LLM didn't include one)
                if tool == "get_school_full_details" and res.get("lat") and res.get("lon"):
                    # Only inject if LLM didn't already include a map
                    if "<map>" not in text:
                        school = {
                            "name": res.get("school_name", "School"),
                            "lat": res.get("lat"),
                            "lon": res.get("lon"),
                            "subdistrict": res.get("subdistrict"),
                            "district": res.get("district"),
                            "province": res.get("province"),
                            "postcode": res.get("postcode")
                        }
                        map_json = self._generate_map_json([school])
                        text += f"\n\n<map>{map_json}</map>"
                        logger.info("📍 Map widget added as fallback (LLM didn't include)")
                
                # FALLBACK: Chart Widget Injection (only if LLM didn't include one)
                # Ranking Chart - fallback for ranking tool
                if tool == "ranking" and res.get("ranking") and "<chart>" not in text:
                    ranking_data = res.get("ranking", [])
                    chart_data = []
                    for item in ranking_data[:10]: # Top 10
                         name = item.get("name", "")
                         if '|' in name: # Clean up name if pipeline format
                             name = name.split('|')[1].strip() if len(name.split('|')) > 1 else name
                         value = item.get("count", 0)
                         chart_data.append({"name": name, "value": value})
                    
                    if chart_data:
                        title = "น้อยที่สุด" if res.get("order") == "least" else "มากที่สุด"
                        chart_json = json.dumps({
                            "type": "bar",
                            "data": chart_data,
                            "title": f"สถิติ{title}"
                        }, ensure_ascii=False)
                        text += f"\n\n<chart>{chart_json}</chart>"
                        logger.info("📊 Chart widget added as fallback (LLM didn't include)")
                        
                # Comparison Chart (Region/Province/School) - ALWAYS SHOW
                elif tool == "compare":
                    e1 = res.get("entity1", {})
                    e2 = res.get("entity2", {})
                    metric = res.get("metric", "value")
                    
                    name1 = e1.get("name", "Entity 1")
                    name2 = e2.get("name", "Entity 2")
                    
                    # Extract total value safely - handle None data
                    data1 = e1.get("data") or {}
                    data2 = e2.get("data") or {}
                    
                    # Try multiple possible keys for the value
                    val1 = data1.get("total_schools", 0) or data1.get("total_students", 0) or data1.get("total_teachers", 0) or data1.get("total", 0) or data1.get("count", 0)
                    val2 = data2.get("total_schools", 0) or data2.get("total_students", 0) or data2.get("total_teachers", 0) or data2.get("total", 0) or data2.get("count", 0)
                    
                    chart_data = [
                        {"name": name1, "value": val1},
                        {"name": name2, "value": val2}
                    ]
                    
                    if val1 > 0 or val2 > 0:
                        chart_title = f"เปรียบเทียบ{metric}"
                        chart_json = json.dumps({
                            "type": "bar",
                            "data": chart_data,
                            "title": chart_title
                        }, ensure_ascii=False)
                        if "<chart>" not in text:
                            text += f"\n\n<chart>{chart_json}</chart>"
                            logger.info(f"📊 Comparison chart injected: {name1}={val1}, {name2}={val2}")
                    if is_explicit_chart_req:
                        by_gender = res.get("by_gender", {})
                        male = by_gender.get('male', 0)
                        female = by_gender.get('female', 0)
                        
                        if male > 0 or female > 0:
                            chart_data = [
                                {"name": "ชาย", "value": male},
                                {"name": "หญิง", "value": female}
                            ]
                            chart_json = json.dumps({
                               "type": "pie",
                               "data": chart_data,
                               "title": "สัดส่วนนักเรียนแยกตามเพศ"
                           }, ensure_ascii=False)
                            if "<chart>" not in text:
                               text += f"\n\n<chart>{chart_json}</chart>"
                            
        except Exception as e:
            logger.error(f"❌ Failed to inject widgets: {e}")
            
        return text
    
    def _format_fallback_response(self, results: List[Dict], question: str = "") -> str:
        """Fallback response formatting when LLM fails - Balanced, concise, formal-friendly"""
        parts = []
        q = (question or "").strip()
        q_lower = q.lower()

        def has_any(keywords: List[str]) -> bool:
            return any(k in q for k in keywords)

        ask_max = has_any(["มากที่สุด", "สูงที่สุด", "มากสุด", "สูงสุด"])
        ask_min = has_any(["น้อยที่สุด", "ต่ำที่สุด", "น้อยสุด", "ต่ำสุด"])
        ask_grade_which = has_any(["ชั้นไหน", "ระดับชั้นไหน"])
        ask_gender_male = has_any(["เพศชาย", "ชาย"])
        ask_gender_female = has_any(["เพศหญิง", "หญิง"])
        ask_person_type = has_any(["ประเภท", "ตำแหน่ง", "กลุ่มบุคลากร", "ประเภทไหน"])

        def normalize_school_label(name: str) -> str:
            if not name:
                return ""
            if "โรงเรียน" in name:
                return name
            return f"โรงเรียน{name}"

        def short_grade_label(grade: str) -> str:
            if not grade:
                return ""
            g = grade.strip()
            g = g.replace("ประถมศึกษาปีที่", "ป.")
            g = g.replace("มัธยมศึกษาปีที่", "ม.")
            g = g.replace("อนุบาลปีที่", "อนุบาล ")
            g = g.replace("อนุบาล", "อนุบาล ")
            g = g.replace("ประกาศนียบัตรวิชาชีพชั้นสูงชั้นปีที่", "ปวส")
            g = g.replace("ประกาศนียบัตรวิชาชีพปีที่", "ปวช")
            return " ".join(g.split())

        def grade_token(value: str) -> str:
            if not value:
                return ""
            g = value.replace(" ", "")
            g = g.replace("ประถมศึกษาปีที่", "ป")
            g = g.replace("มัธยมศึกษาปีที่", "ม")
            g = g.replace("อนุบาลปีที่", "อ")
            g = g.replace("อนุบาล", "อ")
            g = g.replace("ประกาศนียบัตรวิชาชีพชั้นสูงชั้นปีที่", "ปวส")
            g = g.replace("ประกาศนียบัตรวิชาชีพปีที่", "ปวช")
            g = g.replace(".", "")
            m = re.search(r'(ปวช|ปวส|ป|ม|อ)?(\d+)', g)
            if m:
                prefix = m.group(1) or ""
                return f"{prefix}{m.group(2)}"
            return g

        def grade_match(target: str, candidate: str) -> bool:
            if not target or not candidate:
                return False
            t = grade_token(target)
            c = grade_token(candidate)
            if t and c and t == c:
                return True
            return target in candidate or candidate in target

        def pick_grade_extreme(breakdown: Dict[str, Dict[str, Any]], mode: str, gender_key: Optional[str] = None):
            if not breakdown:
                return None
            best_grade = None
            best_val = None
            for g, stats in breakdown.items():
                val = stats.get(gender_key, stats.get("total", 0)) if gender_key else stats.get("total", 0)
                if best_val is None:
                    best_val = val
                    best_grade = g
                    continue
                if mode == "max" and val > best_val:
                    best_val = val
                    best_grade = g
                if mode == "min" and val < best_val:
                    best_val = val
                    best_grade = g
            if best_grade is None:
                return None
            return {"grade": best_grade, "count": best_val or 0}
        
        list_tools = {"search_schools", "list_schools", "advanced_school_search", "filter_schools"}
        for result in results:
            tool = result.get("tool", "unknown")
            summary = result.get("ai_summary")
            if summary and tool not in list_tools:
                parts.append(summary)
                continue

            # Check for suggestions first (Global Handler)
            suggestions = result.get("suggestions")
            if suggestions:
                search_query = result.get("query", {}).get("school_name") or result.get("school_name", "ที่ค้นหา")
                
                # AUTO-SELECT: If only 1 suggestion and it's very similar, use it directly with disclaimer
                if len(suggestions) == 1:
                    s = suggestions[0]
                    matched_name = s.get('name', 'Unknown')
                    province = s.get('province', '')
                    school_id = s.get('school_id', '')
                    
                    # Show data with fuzzy match disclaimer
                    text = f"ไม่พบ '{search_query}' โดยตรง แต่พบข้อมูลใกล้เคียงดังนี้ครับ\n\n"
                    text += f"**{matched_name}**"
                    if province:
                        text += f" (จ.{province})"
                    if school_id:
                        text += f"\n- รหัสโรงเรียน: `{school_id}`"
                    
                    # Add available details from suggestion
                    if s.get('district'):
                        text += f"\n- อำเภอ: {s['district']}"
                    if s.get('total_students'):
                        text += f"\n- จำนวนนักเรียน: {s['total_students']:,} คน"
                    if s.get('total_teachers'):
                        text += f"\n- จำนวนครู: {s['total_teachers']:,} คน"
                    
                    text += "\n\nหากต้องการข้อมูลเพิ่มเติมเกี่ยวกับโรงเรียนนี้ บอกได้เลยครับ"
                    parts.append(text)
                    continue
                
                # MULTIPLE SUGGESTIONS: Ask user to select
                text = f"ไม่พบข้อมูล '{search_query}' ครับ แต่พบโรงเรียนชื่อใกล้เคียงดังนี้\n\n"
                text += "| ลำดับ | ชื่อโรงเรียน | จังหวัด |\n|:--:|:--|:--|\n"
                for i, s in enumerate(suggestions[:5], 1):
                    text += f"| {i} | {s.get('name','')} | {s.get('province','-')} |\n"
                text += "\nต้องการโรงเรียนไหนครับ (ตอบเป็นลำดับหรือชื่อเต็มได้เลย)"
                parts.append(text)
                continue

            # Check for AMBIGUITY (Multiple exact matches)
            if result.get("ambiguous"):
                choices = result.get("choices", [])
                search_query = result.get("query", {}).get("school_name")
                text = f"พบชื่อที่ตรงกันหลายแห่ง ({len(choices)} แห่ง) เพื่อความถูกต้อง กรุณาเลือกโรงเรียนครับ\n\n"
                text += "| ลำดับ | ชื่อโรงเรียน | จังหวัด | อำเภอ | หมายเหตุ |\n|:--:|:--|:--|:--|:--|\n"
                for i, c in enumerate(choices[:10], 1):  # Limit to 10 choices
                    name = c.get('school_name') or c.get('name', '')
                    province = c.get('province', 'ไม่ระบุจังหวัด')
                    district = c.get('district', '-')
                    metrics = []
                    if c.get('total_students'):
                        metrics.append(f"นักเรียน {c['total_students']:,}")
                    if c.get('total_teachers'):
                        metrics.append(f"ครู {c['total_teachers']:,}")
                    note = ", ".join(metrics) if metrics else "-"
                    text += f"| {i} | {name} | {province} | {district} | {note} |\n"
                
                text += "\nตอบเป็นลำดับหรือชื่อเต็มพร้อมจังหวัดได้เลยครับ"
                
                # Generate Map for Choices (Multi-Marker)
                try:
                    valid_schools = []
                    for c in choices[:10]: # Limit to top 10 matches
                        lat = c.get('latitude') or c.get('lat')
                        lon = c.get('longitude') or c.get('lon') or c.get('lng')
                        if lat and lon:
                            valid_schools.append({
                                "name": c.get('school_name') or c.get('name', 'Unknown'),
                                "lat": lat,
                                "lon": lon,
                                "province": c.get('province'),
                                "district": c.get('district')
                            })
                    
                    if valid_schools:
                        map_json = self._generate_map_json(valid_schools)
                        text += f"\n\n<map>{map_json}</map>"
                except Exception as e:
                    logger.error(f"Failed to generate ambiguous map: {e}")

                parts.append(text)
                continue

            # Generic error handling (avoid exposing raw trace)
            if result.get("error"):
                err = str(result.get("error"))
                if "school_name" in err or "School name is required" in err:
                    parts.append("ต้องการชื่อโรงเรียนไหนครับ")
                elif "province" in err:
                    parts.append("ต้องการระบุจังหวัดไหนครับ")
                else:
                    parts.append("ขออภัยครับ ระบบประมวลผลไม่สำเร็จ ลองถามใหม่หรือระบุให้ชัดขึ้นได้ไหมครับ")
                continue
            
            if tool == "count_teachers":
                total = result.get("total_teachers", 0)
                by_gender = result.get("by_gender", {})
                by_person_type = result.get("by_person_type", {})
                query = result.get("query", {}) or {}
                school_count = result.get("school_count", 0) or result.get("total_found", 0)

                scope = ""
                if query.get("school_name"):
                    scope = f"{normalize_school_label(query.get('school_name'))}"
                elif query.get("province"):
                    scope = f"จังหวัด{query.get('province')}"
                elif query.get("region"):
                    scope = f"{query.get('region')}"
                elif query.get("district"):
                    scope = f"อำเภอ{query.get('district')}"

                if scope:
                    text = f"{scope}มีครูทั้งหมด **{total:,}** คนครับ"
                else:
                    text = f"จำนวนครูทั้งหมด **{total:,}** คนครับ"

                if by_gender and (by_gender.get("male") or by_gender.get("female")):
                    text += f"\n- ชาย: {by_gender.get('male', 0):,} คน\n- หญิง: {by_gender.get('female', 0):,} คน"

                if ask_person_type and by_person_type:
                    top_type = max(by_person_type.items(), key=lambda kv: kv[1].get("total", 0))
                    text += f"\nประเภทที่มีจำนวนมากที่สุดคือ **{top_type[0]}** ({top_type[1].get('total', 0):,} คน)"

                if total == 0 and school_count:
                    text += f"\nพบโรงเรียน {school_count:,} แห่งในขอบเขตนี้ แต่ยังไม่มีข้อมูลครูที่บันทึกไว้ครับ"

                if total > 0:
                    text += "\nหากต้องการแยกตามประเภทบุคลากร เพศ หรืออำเภอ/เขต แจ้งได้เลยครับ"

                parts.append(text)
                    
            elif tool == "count_students":
                total = result.get("total_students", 0)
                by_gender = result.get("by_gender", {})
                male = by_gender.get('male', 0)
                female = by_gender.get('female', 0)
                query = result.get("query", {}) or {}
                grade = query.get("grade")
                gender = query.get("gender")
                breakdown = result.get("student_breakdown") or {}
                school_count = result.get("school_count", 0) or result.get("total_found", 0)

                scope = ""
                if query.get("school_name"):
                    scope = f"{normalize_school_label(query.get('school_name'))}"
                elif query.get("province"):
                    scope = f"จังหวัด{query.get('province')}"
                elif query.get("region"):
                    scope = f"{query.get('region')}"
                elif query.get("district"):
                    scope = f"อำเภอ{query.get('district')}"

                grade_label = short_grade_label(grade) if grade else ""
                gender_label = ""
                if gender == "ชาย" or (ask_gender_male and not ask_gender_female):
                    gender_label = "เพศชาย"
                elif gender == "หญิง" or (ask_gender_female and not ask_gender_male):
                    gender_label = "เพศหญิง"

                subject = "นักเรียน"
                if grade_label:
                    subject += f"ชั้น {grade_label}"
                if gender_label:
                    subject += f" {gender_label}"

                if scope:
                    text = f"{scope}มี{subject}ทั้งหมด **{total:,}** คนครับ"
                else:
                    text = f"จำนวน{subject}ทั้งหมด **{total:,}** คนครับ"

                if not gender_label and male > 0 and female > 0:
                    text += f"\n- ชาย: {male:,} คน\n- หญิง: {female:,} คน"

                # If asking for extremes by grade, compute from breakdown (if available)
                if breakdown and (ask_max or ask_min or ask_grade_which):
                    gender_key = "male" if ask_gender_male and not ask_gender_female else "female" if ask_gender_female and not ask_gender_male else None
                    if ask_max:
                        top = pick_grade_extreme(breakdown, "max", gender_key)
                        if top:
                            text += f"\nชั้นที่มีนักเรียนมากที่สุดคือ **{top['grade']}** ({top['count']:,} คน)"
                    if ask_min:
                        bottom = pick_grade_extreme(breakdown, "min", gender_key)
                        if bottom:
                            text += f"\nชั้นที่มีนักเรียนน้อยที่สุดคือ **{bottom['grade']}** ({bottom['count']:,} คน)"

                if total == 0 and school_count:
                    text += f"\nพบโรงเรียน {school_count:,} แห่งในขอบเขตนี้ แต่ยังไม่มีข้อมูลนักเรียนที่บันทึกไว้ครับ"

                if total > 0:
                    text += "\nถ้าต้องการแยกตามระดับชั้น เพศ หรืออำเภอ/เขต ผมช่วยแยกให้ได้ครับ"

                parts.append(text)
                    
            elif tool == "get_school_full_details":
                found = result.get("found", False)
                if found:
                    name = result.get("school_name", "")
                    province = result.get("province", "")
                    district = result.get("district", "")
                    agency = result.get("agency", "")
                    total_students = result.get("total_students", 0)
                    total_teachers = result.get("total_teachers", 0)
                    ratio = result.get("ratio", 0)
                    
                    text = f"โรงเรียน **{name}**"
                    if district and province:
                        text += f" ตั้งอยู่ที่ อ.{district} จ.{province}"
                    elif province:
                        text += f" จ.{province}"
                    text += " ครับ\n\n"
                    
                    if agency: text += f"- **สังกัด:** {agency}\n"
                    if total_students:
                        text += f"- **นักเรียน:** {total_students:,} คน\n"
                    if total_teachers:
                        text += f"- **ครู:** {total_teachers:,} คน\n"
                    if ratio:
                        text += f"- **อัตราส่วนครูต่อนักเรียน:** {ratio}\n"
                    if result.get("lat") and result.get("lon"):
                        text += f"- **พิกัด:** {result.get('lat')}, {result.get('lon')}\n"
                        
                    parts.append(text)
                else:
                    related = result.get("related_summary") or {}
                    text = "ไม่พบข้อมูลโรงเรียนที่ระบุครับ"
                    if related.get("province"):
                        text += f"\nแต่พบข้อมูลภาพรวมจังหวัด{related.get('province')}ดังนี้"
                        text += f"\n- โรงเรียนทั้งหมด: {related.get('total_schools', 0):,} แห่ง"
                        if related.get("total_students"):
                            text += f"\n- นักเรียนทั้งหมด: {related.get('total_students', 0):,} คน"
                        if related.get("total_teachers"):
                            text += f"\n- ครูทั้งหมด: {related.get('total_teachers', 0):,} คน"
                    text += "\nหากต้องการ ลองระบุชื่อโรงเรียนแบบเต็ม หรือบอกจังหวัด/อำเภอเพิ่มเติมได้ครับ"
                    parts.append(text)

            elif tool == "count_schools":
                total = result.get("total_schools", 0)
                by_agency = result.get("by_agency", {})
                by_district = result.get("by_district", {})
                query = result.get("query", {})
                
                # Natural intro with context
                province = query.get("province", "")
                agency = query.get("agency", "")
                agency_name = list(by_agency.keys())[0] if len(by_agency) == 1 else ""
                
                if agency_name and province:
                    text = f"{province}มีโรงเรียนในสังกัด{agency_name} ทั้งหมด **{total:,}** แห่งครับ"
                elif province:
                    text = f"{province}มีโรงเรียนทั้งหมด **{total:,}** แห่งครับ"
                else:
                    text = f"มีโรงเรียนทั้งหมด **{total:,}** แห่งครับ"
                
                # Show by_district if available (more useful breakdown)
                if by_district and len(by_district) > 1:
                    text += " แบ่งตามอำเภอ/เขตที่มีมากที่สุดได้ดังนี้"
                    text += "\n\n| อำเภอ/เขต | จำนวน |\n| --- | --- |"
                    for dist, count in list(by_district.items())[:7]:
                        text += f"\n| {dist} | {count:,} |"
                    # Add insight
                    top_district = list(by_district.keys())[0] if by_district else ""
                    if top_district:
                        text += f"\n\n{top_district}มีโรงเรียนมากที่สุด หากต้องการดูรายชื่อโรงเรียนในพื้นที่ใด ถามได้เลยครับ"
                elif len(by_agency) > 1:
                    # Show by_agency if multiple
                    text += " แบ่งตามสังกัดได้ดังนี้"
                    text += "\n\n| สังกัด | จำนวน |\n| --- | --- |"
                    for ag, count in list(by_agency.items())[:7]:
                        text += f"\n| {ag} | {count:,} |"
                    # Add insight
                    top_agency = list(by_agency.keys())[0] if by_agency else ""
                    if top_agency:
                        text += f"\n\n{top_agency}มีจำนวนมากที่สุด หากต้องการดูรายละเอียดเพิ่มเติม ถามได้เลยครับ"
                else:
                    # Single agency - add general insight
                    text += f"\n\nหากต้องการดูรายชื่อโรงเรียนหรือข้อมูลอื่นๆ สามารถถามได้เลยครับ"
                
                parts.append(text)

            elif tool == "get_province_summary":
                summary = result.get("summary", {}) or {}
                province = summary.get("province") or result.get("query", {}).get("province") or ""
                schools = summary.get("schools", {}) or {}
                students = summary.get("students", {}) or {}
                teachers = summary.get("teachers", {}) or {}

                text = f"สรุปภาพรวมจังหวัด{province}ครับ"
                text += f"\n- โรงเรียนทั้งหมด: {schools.get('total', 0):,} แห่ง"
                text += f"\n- นักเรียนทั้งหมด: {students.get('total', 0):,} คน"
                text += f"\n- ครูทั้งหมด: {teachers.get('total', 0):,} คน"

                if ask_person_type and teachers.get("by_person_type"):
                    top_type = max(teachers["by_person_type"].items(), key=lambda kv: kv[1].get("total", 0))
                    text += f"\nประเภทครูที่มีจำนวนมากที่สุดคือ **{top_type[0]}** ({top_type[1].get('total', 0):,} คน)"

                text += "\nหากต้องการเจาะลึกระดับอำเภอ/สังกัด หรือแยกเพศ แจ้งได้เลยครับ"

                parts.append(text)

            elif tool == "get_grade_distribution":
                distribution = result.get("distribution") or []
                query = result.get("query", {}) or {}
                grade = query.get("grade")
                school_name = result.get("school_name") or query.get("school_name")
                related = result.get("related_summary") or {}

                # Build breakdown dict for easier computation
                breakdown = {}
                for item in distribution:
                    g = item.get("grade") or ""
                    breakdown[g] = {
                        "total": item.get("count", 0),
                        "male": item.get("male", 0),
                        "female": item.get("female", 0)
                    }

                scope = ""
                if school_name:
                    scope = normalize_school_label(school_name)
                elif query.get("province"):
                    scope = f"จังหวัด{query.get('province')}"
                elif query.get("district"):
                    scope = f"อำเภอ{query.get('district')}"

                if grade and breakdown:
                    # Grade-specific query
                    target = None
                    for g in breakdown.keys():
                        if grade_match(grade, g):
                            target = g
                            break
                    if target:
                        stats = breakdown[target]
                        grade_label = short_grade_label(target)
                        gender_key = "male" if ask_gender_male and not ask_gender_female else "female" if ask_gender_female and not ask_gender_male else None
                        count = stats.get(gender_key, stats.get("total", 0)) if gender_key else stats.get("total", 0)
                        gender_label = "เพศชาย" if gender_key == "male" else "เพศหญิง" if gender_key == "female" else ""
                        if scope:
                            text = f"{scope}มีนักเรียนชั้น {grade_label} {gender_label}ทั้งหมด **{count:,}** คนครับ"
                        else:
                            text = f"นักเรียนชั้น {grade_label} {gender_label}ทั้งหมด **{count:,}** คนครับ"
                        parts.append(text)
                        continue

                if breakdown and (ask_max or ask_min or ask_grade_which):
                    gender_key = "male" if ask_gender_male and not ask_gender_female else "female" if ask_gender_female and not ask_gender_male else None
                    text = f"สรุประดับชั้น{('ของ' + scope) if scope else ''}ครับ"
                    if ask_max:
                        top = pick_grade_extreme(breakdown, "max", gender_key)
                        if top:
                            text += f"\nชั้นที่มีนักเรียนมากที่สุดคือ **{top['grade']}** ({top['count']:,} คน)"
                    if ask_min:
                        bottom = pick_grade_extreme(breakdown, "min", gender_key)
                        if bottom:
                            text += f"\nชั้นที่มีนักเรียนน้อยที่สุดคือ **{bottom['grade']}** ({bottom['count']:,} คน)"
                    parts.append(text)
                elif breakdown:
                    # Default: show top 6 grades
                    items = sorted(breakdown.items(), key=lambda kv: kv[1].get("total", 0), reverse=True)[:6]
                    header = f"จำนวนนักเรียนแยกตามระดับชั้น{('ของ' + scope) if scope else ''} (แสดง 6 อันดับแรก)"
                    text = f"{header}\n\n| ระดับชั้น | จำนวน |\n| --- | ---: |"
                    for g, stats in items:
                        text += f"\n| {g} | {stats.get('total', 0):,} |"
                    parts.append(text)
                else:
                    if related:
                        rel_scope = ""
                        if related.get("school_name"):
                            rel_scope = normalize_school_label(related.get("school_name"))
                        elif related.get("district") and related.get("province"):
                            rel_scope = f"อำเภอ{related.get('district')} จ.{related.get('province')}"
                        elif related.get("province"):
                            rel_scope = f"จังหวัด{related.get('province')}"

                        total_students = related.get("total_students", 0)
                        by_gender = related.get("by_gender", {})
                        text = "ยังไม่มีข้อมูลแยกระดับชั้นในระบบตอนนี้ครับ"
                        if rel_scope:
                            text += f" แต่พบข้อมูลภาพรวมของ{rel_scope}ดังนี้"
                        else:
                            text += " แต่พบข้อมูลภาพรวมดังนี้"
                        text += f"\n- นักเรียนทั้งหมด: {total_students:,} คน"
                        if by_gender and (by_gender.get("male") or by_gender.get("female")):
                            text += f"\n- ชาย: {by_gender.get('male', 0):,} คน\n- หญิง: {by_gender.get('female', 0):,} คน"
                        text += "\nหากต้องการ ระบุโรงเรียนหรือระดับชั้นที่ต้องการได้ครับ"
                        parts.append(text)
                    else:
                        parts.append("ยังไม่มีข้อมูลแยกระดับชั้นในขอบเขตที่ระบุครับ แต่สามารถระบุโรงเรียนหรือจังหวัดให้ชัดขึ้นได้ครับ")
                        
            elif tool == "filter_schools":
                # Use the pre-calculated AI summary from tool_executor which handles total vs limit correctly
                summary = result.get("ai_summary", "")
                schools = result.get("schools", [])
                
                if summary:
                    text = f"{summary}\n\n"
                else:
                    total_found = result.get("total_found", 0) or len(schools)
                    showing = len(schools)
                    if total_found > showing:
                         text = f"พบตามเงื่อนไขทั้งหมด **{total_found:,}** แห่ง (แสดง {showing} รายการแรก)\n\n"
                    else:
                         text = f"พบตามเงื่อนไขทั้งหมด **{total_found:,}** แห่ง\n\n"

                if schools:
                    text += "| ลำดับ | ชื่อโรงเรียน | จังหวัด | นักเรียน | ครู | \n| :---: | :--- | :--- | ---: | ---: |"
                    for i, s in enumerate(schools[:10], 1):
                        name = s.get('school_name') or s.get('name', 'ไม่ระบุ')
                        prov = s.get('province', '-')
                        st_count = s.get('total_students', 0) or 0
                        te_count = s.get('total_teachers', 0) or 0
                        text += f"\n| {i} | {name} | {prov} | {st_count:,} | {te_count:,} |"
                    
                parts.append(text)

            elif tool in ["search_schools", "list_schools", "advanced_school_search", "search_schools"]:
                schools = result.get("schools") or result.get("results", [])
                total_count = result.get("total_count") or result.get("total_found") or len(schools)
                displayed_count = len(schools)
                
                # Helper to format count (handle int vs string)
                def fmt_count(val):
                    if isinstance(val, (int, float)):
                        return f"{val:,}"
                    return str(val)

                if schools:
                    # Logic: if total_count is a number and > displayed, OR if it's a string (implying "50+")
                    is_more = False
                    if isinstance(total_count, (int, float)) and total_count > displayed_count:
                        is_more = True
                    elif isinstance(total_count, str) and "+" in total_count:
                        is_more = True

                    if is_more:
                        text = f"พบโรงเรียนทั้งหมด **{fmt_count(total_count)}** แห่งครับ (แสดง {displayed_count} รายการแรก)"
                    else:
                         text = f"พบโรงเรียน **{fmt_count(total_count)}** แห่งครับ รายชื่อมีดังนี้"
                        
                    text += "\n\n| ลำดับ | ชื่อโรงเรียน | จังหวัด | นักเรียน | ครู |\n| :---: | :--- | :--- | ---: | ---: |"
                    
                    for i, s in enumerate(schools[:10], 1):
                        name = s.get('school_name') or s.get('name', 'ไม่ระบุ')
                        prov = s.get('province', '-')
                        st_count = s.get('total_students', 0) or 0
                        te_count = s.get('total_teachers', 0) or 0
                        text += f"\n| {i} | {name} | {prov} | {st_count:,} | {te_count:,} |"
                        
                    # Add insight
                        if s.get('province'):
                            text += f" ({s['province']})"
                    # Add insight
                    if total_count > displayed_count:
                        text += f"\n\nยังมีอีก **{total_count - displayed_count:,}** แห่ง หากต้องการดูเพิ่มเติม สามารถถามได้ครับ"
                    else:
                        text += f"\n\nหากต้องการทราบรายละเอียดของโรงเรียนใดโรงเรียนหนึ่ง หรือข้อมูลจำนวนนักเรียน/ครู สามารถถามได้เลยครับ"
                    parts.append(text)
                        
            elif tool == "ranking":
                ranking = result.get("ranking", [])
                order_text = "มากที่สุด" if result.get("order") == "most" else "น้อยที่สุด"
                metric = result.get("metric")
                scope = result.get("scope", "school")
                if scope in ["province", "provinces"]:
                    subject_text = "จังหวัด"
                elif scope in ["district", "districts"]:
                    subject_text = "อำเภอ"
                elif scope in ["subdistrict", "subdistricts"]:
                    subject_text = "ตำบล"
                elif scope in ["region", "regions"]:
                    subject_text = "ภาค"
                else:
                    subject_text = "โรงเรียน"

                if metric == "schools":
                    metric_text = "โรงเรียน"
                    unit_text = "แห่ง"
                elif metric == "ratio":
                    metric_text = "อัตราส่วนครูต่อนักเรียน"
                    unit_text = "อัตราส่วน"
                else:
                    metric_text = "นักเรียน" if metric == "students" else "ครู"
                    unit_text = "คน"
                
                # Intro
                text = f"จากการจัดอันดับข้อมูล พบว่า{subject_text}ที่มีจำนวน{metric_text}{order_text} มีดังนี้ครับ"
                
                # List
                top_school = ""
                top_count = 0
                top_ratio = None
                for item in ranking:
                    rank = item['rank']
                    name = item['name']
                    count = item['count']
                    if metric == "ratio":
                        if isinstance(count, (int, float)) and count > 0:
                            ratio_display = f"1:{max(1, round(1 / count))}"
                        else:
                            ratio_display = "-"
                        text += f"\n{rank}. {name}: {ratio_display}"
                    else:
                        text += f"\n{rank}. {name}: {count:,} {unit_text}"
                    if rank == 1:
                        top_school = name
                        top_count = count
                        if metric == "ratio":
                            top_ratio = count
                
                # Outro (Insight)
                if top_school:
                    if metric == "ratio" and isinstance(top_ratio, (int, float)) and top_ratio > 0:
                        ratio_display = f"1:{max(1, round(1 / top_ratio))}"
                        text += f"\n\nจะเห็นว่า **{top_school}** ครองอันดับ 1 ด้วยอัตราส่วนประมาณ {ratio_display} ครับ"
                    else:
                        text += f"\n\nจะเห็นว่า **{top_school}** ครองอันดับ 1 ด้วยจำนวน {top_count:,} {unit_text}ครับ"
                    text += "\nหากต้องการทราบข้อมูลเจาะลึกเพิ่มเติม ถามได้เลยครับ"
                    
                parts.append(text)
                    
            elif tool == "get_ratio":
                ratios = result.get("ratios", [])
                if ratios:
                    text = "อัตราส่วนนักเรียนต่อครูครับ\n\n| โรงเรียน | อัตราส่วน | นักเรียน | ครู |\n| --- | --- | --- | --- |"
                    for r in ratios[:5]:
                        school = r.get("school_name", "ไม่ระบุ")
                        ratio = r.get("ratio", 0)
                        students = r.get("students", 0)
                        teachers = r.get("teachers", 0)
                        text += f"\n| {school} | {ratio:.1f}:1 | {students:,} | {teachers:,} |"
                    parts.append(text)
                else:
                    parts.append("ไม่พบข้อมูลอัตราส่วนสำหรับโรงเรียนที่ค้นหาครับ")
            
            # Handle General Chat / General Knowledge in Fallback
            elif tool == "general_chat" or result.get("type") == "general_knowledge":
                # If we are here, it means LLM generation failed (Rate Limit)
                # Return a polite "High Traffic" message instead of "Not Found"
                parts.append("ขออภัยครับ ตอนนี้ระบบ AI มีผู้ใช้งานจำนวนมาก ทำให้ไม่สามารถประมวลผลคำตอบได้ในขณะนี้ โปรดลองใหม่อีกครั้งในอีกสักครู่นะครับ 🙇‍♂️ (Rate Limit Exceeded)")
                    
            elif tool == "compare":
                e1 = result.get("entity1", {})
                e2 = result.get("entity2", {})
                metric_text = "ครู" if result.get("metric") == "teachers" else "นักเรียน"
                text = f"เปรียบเทียบจำนวน{metric_text}ครับ"
                
                if e1.get("data"):
                    d1 = e1["data"]
                    count1 = d1.get("total_teachers", d1.get("total_students", 0))
                    text += f"\n- {e1.get('name', 'A')}: {count1:,} คน"
                else:
                    text += f"\n- {e1.get('name', 'A')}: ไม่พบข้อมูล"
                    
                if e2.get("data"):
                    d2 = e2["data"]
                    count2 = d2.get("total_teachers", d2.get("total_students", 0))
                    text += f"\n- {e2.get('name', 'B')}: {count2:,} คน"
                else:
                    text += f"\n- {e2.get('name', 'B')}: ไม่พบข้อมูล"
                parts.append(text)
        
        return "\n\n".join(parts) if parts else "เสียดายครับ ไม่พบข้อมูลที่ตรงกับเงื่อนไขในฐานข้อมูลครับ ลองปรับคำค้นหาหรือถามข้อมูลในมุมอื่นดูนะครับ 🥺"
    
    def _fallback_response(self, question: str) -> str:
        """Response when no tools were selected - use LLM for general chat"""
        try:
            # Use LLM to generate a natural conversational response
            prompt = f"""คุณคือ "น้องดีโอ" (DO AI) ผู้ช่วย AI อารมณ์ดีจากกระทรวงศึกษาธิการ
            
            **บุคลิกภาพ (สมดุล/สุภาพแต่เป็นกันเอง):**
            - ลงท้ายด้วย "ครับ" แบบพอดี (ห้ามใช้ "คะ/ค่ะ")
            - โทนสุภาพแบบงานบริการ ไม่ใช้คำสแลง
            - ห้ามขึ้นต้นด้วย "สวัสดีครับ" ให้เข้าเรื่องทันทีเพื่อความกระชับ
            
            **สถานการณ์:**
            ผู้ใช้ถามคำถามที่คุณไม่มีเครื่องมือตอบโดยตรง จึงต้องตอบด้วยความรู้ทั่วไป
            
            ข้อความจากผู้ใช้: "{question}"
            
            **การตอบ:**
            - ตอบสุภาพแบบงานบริการ 3–5 ประโยค
            - ถ้าเป็นคำถามทั่วไป ตอบตามความรู้ที่มีแบบตรงคำถาม
            - ถ้าถามข้อมูลลึกที่ต้องใช้ฐานข้อมูล ให้บอกสั้นๆ ว่า "ขออภัยครับ ข้อมูลนี้ผมยังเข้าถึงไม่ได้ในขณะนี้ครับ" และถามกลับแบบสั้น 1 คำถาม
            - ถ้าไม่ได้ถามเรื่องปี/ช่วงเวลา ห้ามพูดถึงปี
            - ไม่ใช้อีโมจิ หรือใช้ได้ไม่เกิน 1 ตัว """

            response = self.llm.generate_content(prompt, timeout=20)
            if response and response.text:
                return response.text
            
        except Exception as e:
            logger.warning(f"⚠️ Fallback LLM failed: {e}")
        
        # Ultimate fallback if LLM also fails
        return (
            "พร้อมช่วยครับ ลองบอกพื้นที่หรือชื่อโรงเรียนที่ต้องการได้นะครับ\n\n"
            "ตัวอย่าง:\n"
            "• 'กรุงเทพมีโรงเรียนกี่แห่ง'\n"
            "• 'โรงเรียน X มีนักเรียนกี่คน'\n"
            "• 'สพป.เชียงใหม่ เขต 1 ครอบคลุมอำเภออะไรบ้าง'"
        )
    
    def _error_response(self, error: str) -> str:
        """Response when an error occurs"""
        return (
            "ขออภัยครับ ตอนนี้ผมประมวลผลไม่สำเร็จ\n\n"
            "ลองถามใหม่อีกครั้ง หรือระบุให้ชัดขึ้น เช่น จังหวัดหรือชื่อโรงเรียนครับ"
        )
