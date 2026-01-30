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
from typing import List, Dict, Any, Optional

from .tools import get_tools_prompt, TOOL_SELECTION_PROMPT, RESPONSE_GENERATION_PROMPT
from .tool_executor import ToolExecutor
from .llm import MultiProviderLLM
from .constants import THAI_PROVINCES, PROVINCE_ALIASES
from .entity_extractor import extract_person_type_smart, extract_grade_smart, extract_area_smart, extract_district_smart, fetch_valid_values, extract_entities_via_llm

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
    
    def process_query(self, question: str, context: Dict[str, Any] = None) -> str:
        """
        Main entry point: Process a user query using LLM + Tools
        
        Args:
            question: User's question in Thai
            context: Optional context (e.g., session memory)
            
        Returns:
            Natural language response
        """
        logger.info(f"🤖 LLM Agent processing: {question}")
        
        try:
            # Step 1: Use LLM to analyze query and select tools
            tool_calls = self._select_tools(question, context)
            
            if not tool_calls:
                logger.warning("⚠️ No tools selected, using fallback")
                return self._fallback_response(question)
            
            logger.info(f"🔧 Selected {len(tool_calls)} tool(s): {[t['name'] for t in tool_calls]}")
            
            # Step 2: Execute all selected tools
            results = []
            deterministic_tools = ['ranking', 'count_students', 'count_teachers', 'get_school_full_details', 'list_schools', 'get_ratio', 'advanced_school_search']
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
            
            # Step 3: Generate Response
            # Hybrid Pro Strategy: We skip deterministic templates to ensure "Pro" quality narration via LLM.
            # (We still keep Fast-Track tool selection for speed)
            if should_use_deterministic and len(results) == 1 and False: # DISABLED for PRO Mode
                 # Only if single tool (if multiple, maybe needed LLM to synthesize?)
                 # For now, let's try deterministic even for single.
                 logger.info("⚡ Using Deterministic Response (Template) - Saving LLM Quota")
                 return self._inject_widgets(self._format_fallback_response(results), results)
            
            # Step 4: Fallback to LLM for complex queries
            response = self._generate_response(question, results)
            
            return response
            
        except Exception as e:
            logger.error(f"❌ LLM Agent error: {e}")
            return self._error_response(str(e))
    
    def _select_tools(self, question: str, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Use LLM to select appropriate tools for the query with retry logic"""
        
        # Format context for prompt
        context_str = "None"
        if context:
            c_items = []
            if context.get("last_school_name"): c_items.append(f"- School: {context['last_school_name']}")
            if context.get("last_province"): c_items.append(f"- Province: {context['last_province']}")
            if context.get("last_district"): c_items.append(f"- District: {context['last_district']}")
            if context.get("last_agency"): c_items.append(f"- Agency: {context['last_agency']}")
            if c_items: context_str = "\n".join(c_items)

        prompt = TOOL_SELECTION_PROMPT.format(
            tools=self.tools_prompt,
            context=context_str,
            question=question
        )
        
        # ⚡ OPTIMIZATION: Try Regex/Keyword Inference FIRST (Save LLM Call)
        # If keywords are strong enough to identify valid tools, skip the LLM selection step.
        inferred_tools = self._infer_tools_from_keywords(question, context)
        if inferred_tools:
            logger.info(f"⚡ Fast-tracked tool selection via keywords: {[t['name'] for t in inferred_tools]}")
            return inferred_tools
            
        logger.info("🤖 Keywords insufficient, falling back to LLM for tool selection...")
        
        # Retry logic: 2 attempts before falling back to keywords
        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = self.llm.generate_content(prompt, timeout=30)  # Increased timeout
                response_text = response.text.strip()
                
                # Extract JSON from response
                tool_calls = self._parse_tool_calls(response_text)
                
                if tool_calls:
                    logger.info(f"✅ LLM tool selection succeeded on attempt {attempt + 1}")
                    
                    # 🧠 Context Injection for LLM results
                    if context and context.get("last_school_name"):
                        for tool in tool_calls:
                            # Only inject for relevant tools if missing
                            if tool['name'] in ['count_students', 'count_teachers', 'get_ratio', 'list_schools']:
                                if 'school_name' not in tool.get('params', {}):
                                    if 'params' not in tool: tool['params'] = {}
                                    tool['params']['school_name'] = context.get("last_school_name")
                                    logger.info(f"🧠 Injected school from context to LLM tool: {tool['params']['school_name']}")
                                    
                    return tool_calls
                    
            except Exception as e:
                logger.warning(f"⚠️ Tool selection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    logger.info("🔄 Retrying tool selection...")
                    continue
        
        # All retries failed - use keyword fallback
        logger.warning("⚠️ LLM tool selection exhausted, using keyword fallback")
        return self._infer_tools_from_keywords(question, context)
    
    def _parse_tool_calls(self, response_text: str) -> List[Dict[str, Any]]:
        """Parse tool calls from LLM response"""
        try:
            # Check for "no tool" type responses - treat as general query
            no_tool_indicators = ['no tool', 'ไม่มี tool', 'cannot', 'ไม่สามารถ', '[]']
            if any(indicator.lower() in response_text.lower() for indicator in no_tool_indicators):
                logger.info("🌐 LLM indicated no tools needed - treating as general query")
                return []
            
            # Try to find JSON array in response
            # Handle cases where LLM adds explanation text
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            if json_match:
                json_str = json_match.group()
                parsed = json.loads(json_str)
                # Validate parsed tools have valid names
                valid_tools = []
                for tool in parsed:
                    if isinstance(tool, dict) and tool.get('name'):
                        # Filter out invalid tool names
                        if 'no tool' not in tool['name'].lower() and 'available' not in tool['name'].lower():
                            valid_tools.append(tool)
                return valid_tools
            
            # Try parsing entire response as JSON
            return json.loads(response_text)
            
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ Failed to parse tool calls: {e}")
            logger.debug(f"Response was: {response_text[:500]}")
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
        elif context and context.get("last_province") and not school_name:
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
        
        logger.info(f"🔍 Extracted entities: school={school_name}, province={province}, district={district}, agency={agency}, grade={grade}, person_type={person_type}, gender={gender if not asks_for_both else 'N/A (asking for total)'}")
        
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
        
        if is_policy_question and not is_data_query:
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
        if any(kw in question_lower for kw in ['อัตราส่วน', 'ต่อครู', 'ratio', 'นักเรียน:ครู', 'ครู:นักเรียน']):
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
            else:
                metric = "students"  # Default to students
            return [{"name": "ranking", "params": {"metric": metric, "order": order, "limit": 5, "province": province}}]
        
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
        if any(kw in question_lower for kw in ['รายละเอียด', 'ที่อยู่', 'เบอร์โทร', 'ติดต่อ', 'เว็บไซต์', 'แผนที่', 'พิกัด', 'รู้จัก', 'ข้อมูลของ']):
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
            'วิทยาลัย','มหาวิทยาลัย', 'สพฐ', 'สังกัด', 'เขต', 'จังหวัด',
            'กรุงเทพ', 'กระบี่', 'รายละเอียด', 'ที่อยู่', 'ติดต่อ'  # Known keywords
        ]
        has_education_context = any(kw in question for kw in education_keywords)
        
        # If no education keywords and no entities extracted, treat as GENERAL
        if not has_education_context and not school_name and not province:
            logger.info(f"🌐 Detected GENERAL query (no education keywords): {question}")
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
            if any(x in school for x in ['การสอน', 'การเรียน', 'การศึกษา', 'อะไรบ้าง', 'อย่างไร', 'ไหม', 'ที่', 'ที่มี', 'ซึ่ง', 'ทั้งหมด', 'กี่', 'ใด', 'นี้', 'นั้น', 'โน้น']):
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
            if len(candidate) > 5 and not re.match(r'^[มป]\s*\d', candidate):
                logger.info(f"🏫 Extracted school (name+number pattern): '{candidate}'")
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
        pattern = r'จังหวัด([ก-๙]+?)(?:มี|มีกี่|อยู่|$|\s)'
        match = re.search(pattern, question)
        if match:
            return match.group(1).strip()
        
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
        """Extract district name from question (Bangkok districts)"""
        import re
        
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
        if match:
            return (match.group(1).strip(), match.group(2).strip())
        
        return ("", "")
    
    def _generate_response(self, question: str, results: List[Dict]) -> str:
        """Use LLM to generate natural language response from tool results"""
        
        # Helper: Check if this is a general chat fallback
        is_general_chat = any(r.get("type") == "general_knowledge" or r.get("tool") == "general_chat" for r in results)
        
        if is_general_chat:
            logger.info("🗣️ Detected General Chat - using conversational prompt")
            prompt = f"""คุณคือ "น้องดีโอ" (DO AI) ผู้ช่วย AI อารมณ์ดีจากกระทรวงศึกษาธิการ
            
            **คำถามจากผู้ใช้:** "{question}"
            
            **คำสั่ง:**
            - ตอบคำถามนี้โดยใช้ความรู้ทั่วไปของคุณ (เพราะไม่มีข้อมูลใน Database โรงเรียน)
            - **เน้นคำสำคัญ:** ให้ใช้ **ตัวหนา (Bold)** กับคำสำคัญ, ชื่อวิชา, หรือประเด็นหลัก เพื่อให้อ่านง่าย
            - ถ้าเป็นเรื่องขั้นตอน, ระเบียบ, หรือความรู้ทั่วไป ให้ตอบให้เป็นประโยชน์ที่สุด
            - ตอบสั้นๆ กระชับ เป็นกันเอง (ลงท้ายด้วย "ครับ")
            - ห้ามบอกว่า "ไม่มีข้อมูล" หรือ "ไม่พบข้อมูล" ให้พยายามตอบเท่าที่ทำได้
            """
        else:
            # Standard Data Response
            data_str = json.dumps(results, ensure_ascii=False, indent=2)
            prompt = RESPONSE_GENERATION_PROMPT.format(
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
        fallback_text = self._format_fallback_response(results)
        return self._inject_widgets(fallback_text, results, question)

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
                
                # 1. Map Widget Injection
                if tool == "get_school_full_details" and res.get("lat") and res.get("lon"):
                    # Single result map
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
                    if "<map>" not in text:
                        text += f"\n\n<map>{map_json}</map>"
                
                # 2. Chart Widget Injection (Restoring Rich UI)
                # Ranking Chart - ALWAYS SHOW (Implied Comparison)
                if tool == "ranking" and res.get("ranking"):
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
                        if "<chart>" not in text:
                            text += f"\n\n<chart>{chart_json}</chart>"
                        
                # Count Schools Chart (Breakdown) - RESTRICTED
                elif tool == "count_schools":
                    # Only show if explicit request OR if it's a comparison context (checked via explicit req for now)
                    if is_explicit_chart_req: 
                        by_district = res.get("by_district", {})
                        by_agency = res.get("by_agency", {})
                        chart_data = []
                        title = "จำนวนโรงเรียน"
                        
                        if by_district and len(by_district) > 1:
                            title = "แยกตามอำเภอ"
                            for k, v in list(by_district.items())[:10]:
                                 chart_data.append({"name": k, "value": v})
                        elif by_agency and len(by_agency) > 1:
                            title = "แยกตามสังกัด"
                            for k, v in list(by_agency.items())[:10]:
                                 chart_data.append({"name": k, "value": v})
                                 
                        if chart_data:
                            chart_json = json.dumps({
                                "type": "bar" if len(chart_data) > 4 else "pie",
                                "data": chart_data,
                                "title": title
                            }, ensure_ascii=False)
                            if "<chart>" not in text:
                                text += f"\n\n<chart>{chart_json}</chart>"

                # Count Teachers Chart (Gender) - RESTRICTED
                elif tool == "count_teachers":
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
                                "title": "สัดส่วนครูแยกตามเพศ"
                            }, ensure_ascii=False)
                             if "<chart>" not in text:
                                text += f"\n\n<chart>{chart_json}</chart>"

                # Comparison Chart (Region/Province/School) - ALWAYS SHOW
                elif tool == "compare":
                    e1 = res.get("entity1", {})
                    e2 = res.get("entity2", {})
                    metric = res.get("metric", "value")
                    
                    name1 = e1.get("name", "Entity 1")
                    name2 = e2.get("name", "Entity 2")
                    
                    # Extract total value safely
                    val1 = e1.get("data", {}).get("total", 0)
                    if not val1 and isinstance(e1.get("data"), dict):
                         # Handle fallback if 'total' key varies (e.g. for simple counts)
                         val1 = e1.get("data", {}).get(f"total_{metric}", 0) or e1.get("data", {}).get("count", 0)

                    val2 = e2.get("data", {}).get("total", 0)
                    if not val2 and isinstance(e2.get("data"), dict):
                         val2 = e2.get("data", {}).get(f"total_{metric}", 0) or e2.get("data", {}).get("count", 0)
                    
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

                # Count Students Chart (Gender) - RESTRICTED
                elif tool == "count_students":
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
    
    def _format_fallback_response(self, results: List[Dict]) -> str:
        """Fallback response formatting when LLM fails - NATURAL FORMAT"""
        parts = []
        
        for result in results:
            tool = result.get("tool", "unknown")

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
                    text = f"📌 **หมายเหตุ:** ไม่พบ '{search_query}' โดยตรง แต่พบข้อมูลใกล้เคียง:\n\n"
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
                    
                    text += "\n\nหากต้องการข้อมูลเพิ่มเติมเกี่ยวกับโรงเรียนนี้ สามารถถามได้เลยครับ 😊"
                    parts.append(text)
                    continue
                
                # MULTIPLE SUGGESTIONS: Ask user to select
                text = f"ไม่พบข้อมูล '{search_query}' ครับ แต่พบโรงเรียนที่มีชื่อใกล้เคียงดังนี้:\n"
                for i, s in enumerate(suggestions[:5], 1):
                    text += f"\n{i}. {s['name']}"
                    if s.get('province'):
                        text += f" (จ.{s['province']})"
                text += "\n\nคุณหมายถึงโรงเรียนไหนครับ? ลองพิมพ์ชื่อโรงเรียนอีกครั้งได้เลยครับ"
                parts.append(text)
                continue

            # Check for AMBIGUITY (Multiple exact matches)
            if result.get("ambiguous"):
                choices = result.get("choices", [])
                search_query = result.get("query", {}).get("school_name")
                text = f"พบโรงเรียนที่มีชื่อหรือคำว่า '{search_query}' จำนวน **{len(choices)}** แห่งครับ เพื่อความถูกต้อง คุณหมายถึงโรงเรียนไหนครับ?\n"
                
                for i, c in enumerate(choices[:10], 1): # Limit to 10 choices
                    name = c.get('school_name') or c.get('name', '')
                    province = c.get('province', 'ไม่ระบุจังหวัด')
                    district = c.get('district', '')
                    
                    text += f"\n{i}. **{name}** (อ.{district} จ.{province})"
                    
                    # Add metrics if available (Immediate Value!)
                    metrics = []
                    if c.get('total_students'):
                        metrics.append(f"นักเรียน {c['total_students']:,} คน")
                    if c.get('total_teachers'):
                        metrics.append(f"ครู {c['total_teachers']:,} คน")
                        
                    if metrics:
                        text += f" - {', '.join(metrics)}"
                    
                text += "\n\nสามารถพิมพ์เลือกเลขข้อ หรือพิมพ์ชื่อเต็มพร้อมจังหวัดได้เลยครับ 😊"
                
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
            
            if tool == "count_teachers":
                total = result.get("total_teachers", 0)
                by_gender = result.get("by_gender", {})
                text = f"มีครูทั้งหมด **{total:,}** คนครับ"
                if by_gender:
                    text += f"\n- ชาย: {by_gender.get('male', 0):,} คน\n- หญิง: {by_gender.get('female', 0):,} คน"
                parts.append(text)
                    
            elif tool == "count_students":
                total = result.get("total_students", 0)
                by_gender = result.get("by_gender", {})
                male = by_gender.get('male', 0)
                female = by_gender.get('female', 0)
                text = f"มีนักเรียนทั้งหมด **{total:,}** คนครับ"
                if male > 0 and female > 0:
                    text += f"\n- ชาย: {male:,} คน\n- หญิง: {female:,} คน"
                elif male > 0 and female == 0:
                    pass
                elif female > 0 and male == 0:
                    pass
                parts.append(text)
                    
            elif tool == "get_school_full_details":
                found = result.get("found", False)
                if found:
                    name = result.get("school_name", "")
                    province = result.get("province", "")
                    district = result.get("district", "")
                    agency = result.get("agency", "")
                    
                    text = f"📍 โรงเรียน **{name}**"
                    if district and province:
                        text += f" ตั้งอยู่ที่ อ.{district} จ.{province}"
                    elif province:
                        text += f" จ.{province}"
                    text += " ครับ\n\n"
                    
                    if agency: text += f"- **สังกัด:** {agency}\n"
                    if result.get("lat") and result.get("lon"):
                        text += f"- **พิกัด:** {result.get('lat')}, {result.get('lon')}\n"
                        
                    parts.append(text)
                else:
                    parts.append("ไม่พบข้อมูลโรงเรียนที่ระบุครับ")

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
                        text += f"\n\nจะเห็นว่า{top_district}มีโรงเรียนมากที่สุด หากต้องการดูรายชื่อโรงเรียนในพื้นที่ใดพื้นที่หนึ่ง ถามได้เลยครับ"
                elif len(by_agency) > 1:
                    # Show by_agency if multiple
                    text += " แบ่งตามสังกัดได้ดังนี้"
                    text += "\n\n| สังกัด | จำนวน |\n| --- | --- |"
                    for ag, count in list(by_agency.items())[:7]:
                        text += f"\n| {ag} | {count:,} |"
                    # Add insight
                    top_agency = list(by_agency.keys())[0] if by_agency else ""
                    if top_agency:
                        text += f"\n\nจะเห็นว่า{top_agency}มีส่วนแบ่งมากที่สุด หากต้องการดูรายละเอียดเพิ่มเติม ถามได้เลยครับ"
                else:
                    # Single agency - add general insight
                    text += f"\n\nหากต้องการดูรายชื่อโรงเรียนหรือข้อมูลอื่นๆ สามารถถามได้เลยครับ"
                
                parts.append(text)
                        
            elif tool in ["search_schools", "list_schools", "advanced_school_search"]:
                schools = result.get("schools") or result.get("results", [])
                total_count = result.get("total_count") or result.get("total_found") or len(schools)  # Use actual count
                displayed_count = len(schools)
                if schools:
                    if total_count > displayed_count:
                        text = f"พบโรงเรียนทั้งหมด **{total_count:,}** แห่งครับ (แสดง {displayed_count} รายการแรก)"
                        # If advanced search, show criteria? No need for now.
                    else:
                        text = f"พบโรงเรียน **{total_count:,}** แห่งครับ รายชื่อมีดังนี้"
                        
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
                metric_text = "นักเรียน" if result.get("metric") == "students" else "ครู"
                
                # Intro
                text = f"จากการจัดอันดับข้อมูล พบว่าโรงเรียนที่มีจำนวน{metric_text}{order_text} มีดังนี้ครับ"
                
                # List
                top_school = ""
                top_count = 0
                for item in ranking:
                    rank = item['rank']
                    name = item['name']
                    count = item['count']
                    text += f"\n{rank}. {name}: {count:,} คน"
                    if rank == 1:
                        top_school = name
                        top_count = count
                
                # Outro (Insight)
                if top_school:
                    text += f"\n\nจะเห็นว่า **{top_school}** ครองอันดับ 1 ด้วยจำนวน {top_count:,} คนครับ"
                    text += "\nหากต้องการทราบข้อมูลเจาะลึกของโรงเรียนเหล่านี้ ถามเพิ่มเติมได้เลยครับ"
                    
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
            
            **บุคลิกภาพ:**
            - 👦 **เป็นผู้ชายเท่านั้น** ลงท้ายด้วย "ครับ" เสมอ (ห้ามใช้ "คะ/ค่ะ" เด็ดขาด)
            - 🤝 **พูดคุยเป็นธรรมชาติ** เหมือนเพื่อนคุยกับเพื่อน ไม่เป็นทางการเกินไป
            - 🚫 **ห้ามขึ้นต้นด้วย "สวัสดีครับ"** ให้เข้าเรื่องทันทีเพื่อความกระชับ
            
            **สถานการณ์:**
            ผู้ใช้ถามคำถามที่คุณไม่มีเครื่องมือตอบโดยตรง จึงต้องตอบด้วยความรู้ทั่วไป
            
            ข้อความจากผู้ใช้: "{question}"
            
            **การตอบ:**
            - ตอบสั้นๆ กระชับ (ไม่เกิน 3 บรรทัด)
            - ถ้าเป็นคำถามทั่วไป ตอบตามความรู้ที่มี
            - ถ้าถามข้อมูลลึกที่ต้องใช้ Database ให้บอกว่า "ขออภัยครับ ข้อมูลนี้ผมยังเข้าถึงไม่ได้ในขณะนี้ครับ" """

            response = self.llm.generate_content(prompt, timeout=20)
            if response and response.text:
                return response.text
            
        except Exception as e:
            logger.warning(f"⚠️ Fallback LLM failed: {e}")
        
        # Ultimate fallback if LLM also fails
        return (
            "สวัสดีครับ! ผมคือน้องดีโอ 🤖 พร้อมช่วยตอบข้อมูลการศึกษาไทยครับ\n\n"
            "💡 **ลองถามได้เลยครับ:**\n"
            "• 'กรุงเทพมีโรงเรียนกี่แห่ง'\n"
            "• 'โรงเรียน X มีนักเรียนกี่คน'\n"
            "• 'สพป.เชียงใหม่ เขต 1 ครอบคลุมอำเภออะไรบ้าง'"
        )
    
    def _error_response(self, error: str) -> str:
        """Response when an error occurs"""
        return (
            "😅 อุ๊ปส์ ขออภัยครับ ผมมีปัญหาในการประมวลผลครับ\n\n"
            "💡 **ลองทำแบบนี้ดูครับ:**\n"
            "• ถามคำถามใหม่อีกครั้ง\n"
            "• ลองเปลี่ยนวิธีถาม เช่น 'โรงเรียนในกรุงเทพ' แทน 'โรงเรียน กทม'\n"
            "• ถามเรื่องอื่นที่สนใจได้เลยครับ 🚀"
        )
