"""InterceptHandlersMixin - Disambiguation + year comparison interceptors."""
import re
import json
import logging
from typing import Dict, List, Optional, Any
from ..core.constants import REGIONS, THAI_PROVINCES, PROVINCE_ALIASES
from ..core.types import ParsedQuery, QueryIntent, QueryLevel
logger = logging.getLogger(__name__)

class InterceptHandlersMixin:
    """Disambiguation selection, year comparison, and active query inference."""


    def _infer_active_query_from_parsed(self, parsed: ParsedQuery, message: str) -> Optional[Dict[str, Any]]:
        """
        Infer a minimal active_query from parser output.
        Used when response comes from cache (no tool execution), so follow-up can still route correctly.
        """
        if not parsed:
            return None

        msg = message or ""
        params: Dict[str, Any] = {}
        if parsed.province:
            params["province"] = parsed.province
        if parsed.region:
            params["region"] = parsed.region
        if parsed.district:
            params["district"] = parsed.district
        if parsed.subdistrict:
            params["subdistrict"] = parsed.subdistrict
        if parsed.agency:
            params["agency"] = parsed.agency
        if parsed.school_name:
            params["school_name"] = parsed.school_name
        if parsed.person_type:
            params["person_type"] = parsed.person_type

        intent = parsed.intent
        tool_name = None

        # Filter intents (preserve threshold for follow-up like "มากกว่า 800 คนล่ะ")
        inferred_metric = "students"
        if any(k in msg for k in ["ครู", "อาจารย์", "บุคลากร"]):
            inferred_metric = "teachers"
        elif any(k in msg for k in ["นักเรียน", "ผู้เรียน", "เด็ก"]):
            inferred_metric = "students"

        if intent == QueryIntent.FILTER_LESS_THAN:
            tool_name = "filter_schools"
            params["operator"] = "lt"
            params["value"] = parsed.threshold or 0
            params["metric"] = inferred_metric
        elif intent == QueryIntent.FILTER_GREATER_THAN:
            tool_name = "filter_schools"
            params["operator"] = "gt"
            params["value"] = parsed.threshold or 0
            params["metric"] = inferred_metric
        elif intent == QueryIntent.FILTER_EQUALS:
            tool_name = "filter_schools"
            params["operator"] = "eq"
            params["value"] = parsed.threshold or 0
            params["metric"] = inferred_metric

        # Ranking intents
        elif intent in [QueryIntent.RANKING_MOST, QueryIntent.RANKING_LEAST]:
            tool_name = "ranking"
            params["order"] = "most" if intent == QueryIntent.RANKING_MOST else "least"
            if any(k in msg for k in ["อัตราส่วน", "ครูต่อ", "นักเรียนต่อครู", "ไม่ทั่วถึง", "ขาดแคลนครู"]):
                params["metric"] = "ratio"
            elif any(k in msg for k in ["ครู", "อาจารย์", "บุคลากร"]):
                params["metric"] = "teachers"
            elif any(k in msg for k in ["นักเรียน", "ผู้เรียน", "เด็ก"]):
                params["metric"] = "students"
            else:
                params["metric"] = "schools"

            if parsed.level == QueryLevel.DISTRICT:
                params["scope"] = "district"
            elif parsed.level == QueryLevel.SUBDISTRICT:
                params["scope"] = "subdistrict"
            elif parsed.level == QueryLevel.REGION:
                params["scope"] = "region"
            else:
                params["scope"] = "province"

        elif intent == QueryIntent.SCHOOL_COUNT:
            tool_name = "count_schools"
        elif intent == QueryIntent.STUDENT_COUNT:
            tool_name = "count_students"
        elif intent == QueryIntent.TEACHER_COUNT:
            tool_name = "count_teachers"
        elif intent == QueryIntent.RATIO:
            tool_name = "get_ratio"
        elif intent == QueryIntent.SCHOOL_LIST:
            tool_name = "list_schools"
        elif intent == QueryIntent.SCHOOL_SEARCH:
            tool_name = "search_schools"
        elif intent == QueryIntent.SCHOOL_DETAIL and parsed.school_name:
            tool_name = "get_school_full_details"
        elif intent == QueryIntent.COUNT:
            # Generic fallback
            if "ครู" in msg:
                tool_name = "count_teachers"
            elif "นักเรียน" in msg:
                tool_name = "count_students"
            else:
                tool_name = "count_schools"

        if not tool_name:
            return None
        return {"name": tool_name, "params": params}
    def _try_disambiguation_intercept(self, message: str, history: List[Dict[str, str]]) -> Optional[str]:
        """
        🆕 Intercept disambiguation selection patterns (e.g., "1", "ข้อ 2").
        Reads stored disambiguation choices from memory (persisted via Redis),
        then re-queries with the resolved school name.
        Returns formatted response string, or None if not a selection pattern.
        """
        import re
        msg = (message or "").strip()
        
        # Check if message is a selection pattern
        sel_match = re.fullmatch(r'(?:ข้อ|อันดับ|ลำดับ|เลือก|หมายเลข)?\s*(\d{1,2})\s*', msg)
        if not sel_match:
            return None
        
        selection_idx = int(sel_match.group(1))
        if selection_idx < 1 or selection_idx > 20:
            return None
        
        # Check if we have stored disambiguation choices in memory
        if not self.memory or not self.memory.last_disambig_choices:
            # Fallback: try parsing from last_ai_response in memory
            last_ai = getattr(self.memory, 'last_ai_response', '') if self.memory else ''
            if not last_ai:
                return None
            
            disambig_markers = [
                "กรุณาเลือก", "พบโรงเรียน", "พบชื่อที่ตรงกัน", "ชื่อใกล้เคียง",
                "ตอบเป็นลำดับ", "เลือกโรงเรียน", "พบโรงเรียนที่ตรงกัน"
            ]
            if not any(marker in last_ai for marker in disambig_markers):
                return None
            
            # Parse table from last_ai_response (4 columns: idx, name, province, district)
            table_rows = re.findall(
                r'\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|',
                last_ai
            )
            choices = []
            for row_idx_str, school_name, province, district in table_rows:
                try:
                    row_idx = int(row_idx_str)
                    choices.append({"idx": row_idx, "name": school_name.strip(), "province": province.strip(), "district": district.strip()})
                except ValueError:
                    continue
            if not choices:
                return None
            self.memory.last_disambig_choices = choices
        
        logger.info(f"📋 [DisambigIntercept] Detected selection: {selection_idx}")
        
        # Find the selected school from stored choices
        selected_school = None
        selected_province = None
        for choice in self.memory.last_disambig_choices:
            idx = choice.get("idx", 0)
            if idx == selection_idx:
                selected_school = choice.get("name", "")
                selected_province = choice.get("province", "")
                selected_district = choice.get("district", "")
                break
        
        if not selected_school:
            logger.warning(f"⚠️ [DisambigIntercept] No choice at index {selection_idx}")
            return None
        
        # Clean up province/district
        if selected_province in ["ไม่ระบุจังหวัด", "-", ""]:
            selected_province = None
        if selected_district in ["-", ""]:
            selected_district = None
        
        logger.info(f"📋 [DisambigIntercept] Selected: {selected_school} ({selected_province}, {selected_district})")
        
        # Reconstruct query with EXACT school name (not original query) to avoid re-disambiguation
        # Use the specific school name + province + district for precise matching
        reconstructed = f"ข้อมูลโรงเรียน{selected_school}"
        if selected_province:
            reconstructed += f" จังหวัด{selected_province}"
        if selected_district:
            reconstructed += f" อำเภอ{selected_district}"
        
        logger.info(f"📋 [DisambigIntercept] Reconstructed: {reconstructed}")
        
        # Update memory with selected school
        self.memory.last_school_name = selected_school
        if selected_province:
            self.memory.last_province = selected_province
        if selected_district:
            self.memory.last_district = selected_district
        # Clear disambiguation state
        self.memory.last_disambig_choices = None
        self.memory.last_disambig_query = None
        
        # Re-query: First try direct tool executor call (bypasses LLM re-disambiguation)
        try:
            if hasattr(self, 'llm_agent') and self.llm_agent and hasattr(self.llm_agent, 'tool_executor'):
                tool_result = self.llm_agent.tool_executor._get_school_full_details(
                    school_name=selected_school,
                    province=selected_province,
                    district=selected_district
                )
                if tool_result and tool_result.get("found"):
                    # Use synthesizer to format the raw result
                    # ResponseSynthesizer is already imported from .search.query_parser at top level, 
                    # but we re-import locally to be safe or just use it. 
                    # For safety against shadowing, we use the global oneline or import it correctly.
                    from .search.query_parser import ResponseSynthesizer
                    synthesizer = ResponseSynthesizer()
                    formatted = synthesizer.synthesize("TOOL_RESULT", tool_result, reconstructed)
                    if formatted:
                        logger.info(f"✅ [DisambigIntercept] Direct tool call succeeded for {selected_school}")
                        return formatted
                    # Fallback: basic formatting
                    lines = [f"📍 **{tool_result.get('school_name', selected_school)}**"]
                    if tool_result.get('province'):
                        lines.append(f"จังหวัด: {tool_result['province']}")
                    if tool_result.get('district'):
                        lines.append(f"อำเภอ/เขต: {tool_result['district']}")
                    if tool_result.get('total_students'):
                        lines.append(f"จำนวนนักเรียน: {tool_result['total_students']:,} คน")
                    if tool_result.get('total_teachers'):
                        lines.append(f"จำนวนครู: {tool_result['total_teachers']:,} คน")
                    if tool_result.get('agency'):
                        lines.append(f"สังกัด: {tool_result['agency']}")
                    if tool_result.get('student_breakdown'):
                        lines.append("\n**จำนวนนักเรียนจำแนกตามชั้น:**")
                        for grade, counts in tool_result['student_breakdown'].items():
                            total = counts if isinstance(counts, int) else counts.get('total', 0)
                            lines.append(f"- {grade}: {total:,} คน")
                    logger.info(f"✅ [DisambigIntercept] Direct formatted for {selected_school}")
                    return "\n".join(lines)
        except Exception as e:
            logger.warning(f"⚠️ [DisambigIntercept] Direct tool call failed: {e}")
        
        # Fallback: re-query via LLM agent
        try:
            if self.use_llm_agent and self.llm_agent:
                context = self.memory.to_dict() if self.memory else {}
                context["selected_school"] = selected_school
                if selected_province:
                    context["selected_province"] = selected_province
                if selected_district:
                    context["selected_district"] = selected_district
                
                llm_response, _ = self.llm_agent.process_query(reconstructed, context=context)
                if llm_response:
                    logger.info(f"✅ [DisambigIntercept] LLM fallback succeeded for {selected_school}")
                    return llm_response
        except Exception as e:
            logger.error(f"❌ [DisambigIntercept] LLM Agent failed: {e}")
        
        return None
    def _try_year_comparison_intercept(self, message: str) -> Optional[str]:
        """
        🆕 Intercept year-comparison queries before LLM agent.
        Detects patterns like "ปี 67 กับ 68" and calls compare_years directly.
        Returns formatted response string, or None if not a year comparison.
        """
        import re
        if not message:
            return None
        
        msg = message.strip()
        
        # Pattern: find 2 different year numbers in the message
        # Match Thai year formats: ปี 67, ปี 2567, 67, 2567
        year_pattern = r'(?:ปี\s*)?(\d{2,4})'
        year_matches = re.findall(year_pattern, msg)
        
        if len(year_matches) < 2:
            return None
        
        # Filter to valid years only
        from ..core.constants import YEAR_ALIASES, AVAILABLE_YEARS
        valid_years = []
        for y in year_matches:
            normalized = YEAR_ALIASES.get(y, y)
            if normalized in AVAILABLE_YEARS and normalized not in valid_years:
                valid_years.append(normalized)
        
        if len(valid_years) < 2:
            return None
        
        # Check if this is actually a comparison context
        compare_keywords = [
            "เปรียบเทียบ", "เทียบ", "ต่างกัน", "แตกต่าง",
            "กับ", "vs", "เทียบกับ", "กี่คน", "กี่แห่ง",
            "เพิ่ม", "ลด", "เปลี่ยน", "ปี"
        ]
        if not any(kw in msg for kw in compare_keywords):
            return None
        
        year1, year2 = valid_years[0], valid_years[1]
        logger.info(f"📅 [YearIntercept] Detected year comparison: {year1} vs {year2}")
        
        # Extract province (if any)
        province = None
        # Common aliases first
        if "กรุงเทพ" in msg:
            province = "กรุงเทพมหานคร"
        elif hasattr(self, 'llm_agent') and self.llm_agent and hasattr(self.llm_agent, 'tool_executor'):
            # Use the tool executor's province normalization
            import re as re2
            # Try to find known province patterns: จังหวัดX, ในX, ของX
            prov_match = re2.search(r'(?:จังหวัด|ใน|ของ)\s*([ก-ฮ]+(?:[ก-ฮ]+)*)', msg)
            if prov_match:
                candidate = prov_match.group(1)
                # Filter out non-province words
                skip_words = ["ปี", "ประเทศ", "ภาค", "ทั้ง", "แต่ละ"]
                if candidate not in skip_words and len(candidate) >= 3:
                    province = candidate
        # Fallback to memory
        if not province and self.memory and self.memory.last_province:
            province = self.memory.last_province
        
        # Extract school name (if any)
        school_name = None
        school_keywords = ["โรงเรียน", "วิทยาลัย", "สถาบัน"]
        for kw in school_keywords:
            if kw in msg:
                # Extract school name after the keyword
                idx = msg.index(kw)
                remaining = msg[idx:]
                # Take until next space-separated keyword or year marker
                parts = remaining.split()
                if len(parts) >= 2:
                    # Take the school name part (skip common Thai suffixes/year markers)
                    school_parts = []
                    stop_words = ["มี", "มีนักเรียน", "มีครู", "ปี", "กี่", "เท่าไหร่", "เท่าไร",
                                  "นักเรียน", "ครู", "จำนวน", "เปรียบเทียบ", "กับ", "vs"]
                    for p in parts:
                        if p in stop_words or re.match(r'^\d{2,4}$', p):
                            break
                        school_parts.append(p)
                    school_name = " ".join(school_parts).strip()
                    if school_name == kw:
                        school_name = None
                break
        
        # Extract metric — if user mentions 2+ metrics, use "all"
        has_student_kw = any(kw in msg for kw in ["นักเรียน", "นร", "เด็ก"])
        has_teacher_kw = any(kw in msg for kw in ["ครู", "อาจารย์"])
        has_school_kw = "โรงเรียน" in msg and not school_name
        metric_count = sum([has_student_kw, has_teacher_kw, has_school_kw])

        if metric_count >= 2:
            metric = "all"
        elif has_student_kw:
            metric = "students"
        elif has_teacher_kw:
            metric = "teachers"
        elif has_school_kw:
            metric = "schools"
        else:
            metric = "all"
        
        logger.info(f"📅 [YearIntercept] Params: province={province}, school={school_name}, metric={metric}")
        
        # Call the tool directly
        try:
            tool_result = self.llm_agent.tool_executor._compare_years(
                year1=year1,
                year2=year2,
                province=province,
                school_name=school_name,
                metric=metric,
            )
            
            if not tool_result or "error" in tool_result:
                error_msg = tool_result.get("error", "ไม่สามารถดึงข้อมูลได้") if tool_result else "ไม่สามารถดึงข้อมูลได้"
                return f"ขออภัยครับ {error_msg}"
            
            # Format response using LLM agent
            import json
            tool_data_str = json.dumps(tool_result, ensure_ascii=False, default=str)
            
            try:
                if hasattr(self, 'llm_agent') and self.llm_agent:
                    response = self.llm_agent._generate_response(
                        message,
                        [tool_result]
                    )
                else:
                    response = None
            except Exception as llm_err:
                logger.warning(f"⚠️ [YearIntercept] LLM formatting failed: {llm_err}")
                response = None
            
            if response:
                return response
            else:
                # Fallback: format manually
                y1_data = tool_result.get("year1", {})
                y2_data = tool_result.get("year2", {})
                diff = tool_result.get("difference", {})
                scope = tool_result.get("scope", "")
                
                lines = [f"📊 เปรียบเทียบข้อมูลปี {y1_data.get('year')} กับ {y2_data.get('year')} ({scope})\n"]
                for key in ["schools", "students", "teachers"]:
                    if key in diff:
                        d = diff[key]
                        label = {"schools": "โรงเรียน", "students": "นักเรียน", "teachers": "ครู"}.get(key, key)
                        v1 = y1_data.get("data", {}).get(key, 0)
                        v2 = y2_data.get("data", {}).get(key, 0)
                        lines.append(f"- {label}: ปี {y1_data.get('year')} = **{v1:,}** → ปี {y2_data.get('year')} = **{v2:,}** ({d['direction']} {abs(d['change']):,}, {d['percent_change']}%)")
                
                return "\n".join(lines)
                
        except Exception as e:
            logger.error(f"❌ [YearIntercept] Error: {e}")
            return None
