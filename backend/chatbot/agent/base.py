"""
🤖 AgentBase – __init__ and process_query() orchestrator.
Extracted from llm_agent.py lines 41-197.
"""

import json
import logging
import os
from typing import Dict, Any, Optional, List

from ..tools import get_tools_prompt
from ..tool_executor import ToolExecutor
from ..core.llm import MultiProviderLLM

logger = logging.getLogger(__name__)


class AgentBase:
    """Base class: init + main orchestrator (process_query)."""

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

            # Step 1.5: Enrich tool params with context
            tool_calls = self._enrich_tool_params(question, tool_calls, context)

            # Step 2: Execute all selected tools
            results = []
            deterministic_tools = [
                'ranking', 'count_students', 'count_teachers',
                'get_school_full_details', 'get_province_summary',
                'get_grade_distribution', 'list_schools',
                'get_ratio', 'advanced_school_search'
            ]
            should_use_deterministic = False

            for tool_call in tool_calls:
                name = tool_call["name"]
                if name in deterministic_tools:
                    should_use_deterministic = True
                result = self.tool_executor.execute(name, tool_call.get("params", {}))
                results.append(result)

            # Step 2.5: self-healing reflection loop for Empty Results
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

            if results and all(is_empty_result(r) for r in results):
                logger.warning("⚠️ All tool results were empty. Triggering Agentic Reflection Loop...")
                reflection_context = dict(context or {})
                reflection_context["reflection_prompt"] = (
                    "คำค้นหาก่อนหน้านี้ไม่พบข้อมูลในฐานข้อมูลเลย (Empty Result). "
                    "กรุณาลองลดเงื่อนไขที่แคบเกินไป เช่น ตัดชื่ออำเภอ/ตำบลออกเพื่อค้นหาทั่วจังหวัด "
                    "หรือถ้ามีชื่อโรงเรียน ให้ระบุเฉพาะชื่อหลักไม่ต้องใส่คำว่า โรงเรียน หรือลองใช้ tool อื่นที่ขอบเขตกว้างขึ้น"
                )
                retry_tool_calls = self._select_tools(question, reflection_context)

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

                    if retry_results and not all(is_empty_result(r) for r in retry_results):
                        logger.info("✅ Reflection try succeeded! Replacing empty results with new data.")
                        tool_calls = retry_tool_calls
                        results = retry_results
                    else:
                        logger.warning("❌ Reflection try also yielded empty data. Falling through to original.")

            # --- Inject Data into Active Query Params for Follow-up Memory ---
            if tool_calls and results:
                try:
                    active_query = tool_calls[0]  # Ensure active_query points to the final tool_call used
                    for t_call, t_res in zip(tool_calls, results):
                        t_name = t_call.get("name")
                        if not isinstance(t_res, dict):
                            continue
                            
                        if t_name == "ranking" and t_res.get("ranking") and len(t_res["ranking"]) > 0:
                            top_item = t_res["ranking"][0]["name"]
                            scope = t_res.get("scope", "")
                            
                            # Safely modify the params dict
                            if "params" not in t_call or not isinstance(t_call["params"], dict):
                                t_call["params"] = {}
                                
                            if scope in ["province", "provinces"]:
                                t_call["params"]["province"] = top_item
                            elif scope in ["district", "districts"]:
                                dist_name = top_item
                                if " - " in dist_name:
                                    parts = dist_name.split(" - ", 1)
                                    if len(parts) == 2:
                                        t_call["params"]["province"] = parts[0]
                                        dist_name = parts[1]
                                t_call["params"]["district"] = dist_name
                            elif scope in ["school", "schools"]:
                                t_call["params"]["school_name"] = top_item
                            elif scope in ["region", "regions"]:
                                t_call["params"]["region"] = top_item
                                
                        elif t_name == "find_best_ratio_schools" and t_res.get("schools") and len(t_res["schools"]) > 0:
                            top_school = t_res["schools"][0]["school_name"]
                            top_prov = t_res["schools"][0].get("province")
                            if "params" not in t_call or not isinstance(t_call["params"], dict):
                                t_call["params"] = {}
                            t_call["params"]["school_name"] = top_school
                            if top_prov:
                                t_call["params"]["province"] = top_prov
                except Exception as mem_e:
                    logger.warning(f"⚠️ Failed to inject top result into active query: {mem_e}")

            # Step 3: Generate Response
            use_deterministic = os.getenv("ENABLE_DETERMINISTIC_RESPONSES", "1") == "1"
            if should_use_deterministic and len(results) == 1 and use_deterministic:
                logger.info("⚡ Deterministic path → Naturalizing with LLM...")
                template_text = self._format_fallback_response(results, question)
                natural_text = self._naturalize_response(template_text, question, results)
                suggestions_list = self._get_proactive_suggestions(tool_calls, results)
                if suggestions_list:
                    natural_text += "\n\n<suggestions>" + json.dumps(suggestions_list, ensure_ascii=False) + "</suggestions>"
                return self._inject_widgets(natural_text, results), active_query

            # Step 4: Fallback to LLM for complex queries
            suggestions_list = self._get_proactive_suggestions(tool_calls, results)
            response = self._generate_response(question, results)
            if suggestions_list:
                response += "\n\n<suggestions>" + json.dumps(suggestions_list, ensure_ascii=False) + "</suggestions>"
            response = self._inject_widgets(response, results, question)

            return response, active_query

        except Exception as e:
            import traceback
            logger.error(f"❌ LLM Agent error: {e}")
            logger.error(f"❌ Full traceback:\n{traceback.format_exc()}")
            return self._error_response(str(e)), None
