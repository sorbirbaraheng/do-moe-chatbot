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

logger = logging.getLogger(__name__)


class LLMAgent:
    """
    LLM-powered agent that intelligently selects and executes tools
    to answer education queries comprehensively.
    """
    
    def __init__(self, qdrant_client, llm: MultiProviderLLM):
        self.tool_executor = ToolExecutor(qdrant_client)
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
            tool_calls = self._select_tools(question)
            
            if not tool_calls:
                logger.warning("⚠️ No tools selected, using fallback")
                return self._fallback_response(question)
            
            logger.info(f"🔧 Selected {len(tool_calls)} tool(s): {[t['name'] for t in tool_calls]}")
            
            # Step 2: Execute all selected tools
            results = []
            for tool_call in tool_calls:
                result = self.tool_executor.execute(
                    tool_call["name"],
                    tool_call.get("params", {})
                )
                results.append(result)
            
            # Step 3: Generate natural language response from results
            response = self._generate_response(question, results)
            
            return response
            
        except Exception as e:
            logger.error(f"❌ LLM Agent error: {e}")
            return self._error_response(str(e))
    
    def _select_tools(self, question: str) -> List[Dict[str, Any]]:
        """Use LLM to select appropriate tools for the query"""
        
        prompt = TOOL_SELECTION_PROMPT.format(
            tools=self.tools_prompt,
            question=question
        )
        
        try:
            response = self.llm.generate_content(prompt, timeout=15)
            response_text = response.text.strip()
            
            # Extract JSON from response
            tool_calls = self._parse_tool_calls(response_text)
            
            return tool_calls
            
        except Exception as e:
            logger.error(f"❌ Tool selection failed: {e}")
            # Fallback: try to infer tool from keywords
            return self._infer_tools_from_keywords(question)
    
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
    
    def _infer_tools_from_keywords(self, question: str) -> List[Dict[str, Any]]:
        """Fallback: Infer tools from keywords when LLM fails"""
        question_lower = question.lower()
        
        # Extract entities from question
        school_name = self._extract_school_name(question)
        province = self._extract_province(question)
        district = self._extract_district(question)
        gender = self._extract_gender(question)
        
        params = {}
        if school_name:
            params["school_name"] = school_name
        if province:
            params["province"] = province
        if district:
            params["district"] = district
        if gender:
            params["gender"] = gender
        
        logger.info(f"🔍 Extracted entities: school={school_name}, province={province}, district={district}, gender={gender}")
        
        # ============================================================
        # PRIORITY ORDER: More specific queries first!
        # ============================================================
        
        # 1. COMPARISON - เปรียบเทียบ
        if any(kw in question_lower for kw in ['เปรียบเทียบ', 'ระหว่าง', 'กับ', 'vs']):
            entities = self._extract_comparison_entities(question)
            metric = "teachers" if any(kw in question for kw in ['ครู', 'อาจารย์']) else "students"
            return [{"name": "compare", "params": {"entity1": entities[0], "entity2": entities[1], "metric": metric}}]
        
        # 2. RATIO - อัตราส่วน (BEFORE ครู detection!)
        if any(kw in question_lower for kw in ['อัตราส่วน', 'ต่อครู', 'ratio', 'นักเรียน:ครู', 'ครู:นักเรียน']):
            return [{"name": "get_ratio", "params": params}]
        
        # 3. RANKING - มากที่สุด/น้อยที่สุด
        if any(kw in question_lower for kw in ['มากที่สุด', 'น้อยที่สุด', 'อันดับ', 'top', 'สูงสุด', 'ต่ำสุด']):
            order = "most" if any(kw in question_lower for kw in ['มากที่สุด', 'สูงสุด', 'top']) else "least"
            # Determine metric from keywords
            if any(kw in question_lower for kw in ['ครู', 'อาจารย์', 'บุคลากร']):
                metric = "teachers"
            elif any(kw in question_lower for kw in ['นักเรียน', 'เด็ก', 'นักศึกษา']):
                metric = "students"
            else:
                metric = "students"  # Default to students
            return [{"name": "ranking", "params": {"metric": metric, "order": order, "limit": 5, "province": province}}]
        
        # 4. TEACHER COUNT
        if any(kw in question_lower for kw in ['ครู', 'อาจารย์', 'บุคลากร', 'ข้าราชการ', 'พนักงาน']):
            return [{"name": "count_teachers", "params": params}]
        
        # 5. STUDENT COUNT
        if any(kw in question_lower for kw in ['นักเรียน', 'ผู้เรียน', 'เด็ก', 'นักศึกษา']):
            return [{"name": "count_students", "params": params}]
        
        # 6. SCHOOL COUNT - include district!
        if any(kw in question_lower for kw in ['กี่โรงเรียน', 'จำนวนโรงเรียน', 'มีโรงเรียน', 'กี่แห่ง', 'กี่โรง', 'สถานศึกษา']):
            return [{"name": "count_schools", "params": {"province": province, "district": district}}]
        
        # 7. SCHOOL LIST - include district!
        if any(kw in question_lower for kw in ['รายชื่อ', 'โรงเรียนอะไรบ้าง', 'มีอะไรบ้าง', 'โรงเรียนใดบ้าง']):
            return [{"name": "list_schools", "params": {"province": province, "district": district, "limit": 10}}]
        
        # 8. CHECK FOR GENERAL/CASUAL QUERIES - Don't search database!
        # If no education-related keywords found, it's likely a general query
        education_keywords = [
            'โรงเรียน', 'นักเรียน', 'ครู', 'อาจารย์', 'สถานศึกษา', 'การศึกษา',
            'วิทยาลัย', 'มหาวิทยาลัย', 'สพฐ', 'สังกัด', 'เขต', 'จังหวัด',
            'กรุงเทพ', 'กระบี่'  # Known provinces in database
        ]
        has_education_context = any(kw in question for kw in education_keywords)
        
        # If no education keywords and no entities extracted, treat as GENERAL
        if not has_education_context and not school_name and not province:
            logger.info(f"🌐 Detected GENERAL query (no education keywords): {question}")
            return []  # Empty = no tools needed, LLM will respond directly
        
        # 9. DEFAULT: search schools (only if there's some context)
        if school_name or province or district:
            return [{"name": "search_schools", "params": params}]
        
        # Final fallback: treat as general if truly nothing matched
        logger.info(f"🌐 Final fallback - treating as GENERAL query: {question}")
        return []
    
    def _extract_school_name(self, question: str) -> Optional[str]:
        """Extract school name from question using patterns"""
        import re
        
        # Pattern: โรงเรียน[ชื่อ] หรือ วิทยาลัย[ชื่อ]
        patterns = [
            r'โรงเรียน([ก-๙a-zA-Z\s]+?)(?:มี|มีกี่|มีจำนวน|อยู่|สังกัด|ตั้งอยู่|ที่อยู่|ทั้งหมด|$)',
            r'วิทยาลัย([ก-๙a-zA-Z\s]+?)(?:มี|มีกี่|มีจำนวน|อยู่|สังกัด|ตั้งอยู่|ที่อยู่|ทั้งหมด|$)',
            r'โรงเรียน([ก-๙a-zA-Z\s]+)',
            r'วิทยาลัย([ก-๙a-zA-Z\s]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, question)
            if match:
                school = match.group(1).strip()
                if len(school) > 2:  # At least 3 chars
                    return school
        
        return None
    
    def _extract_province(self, question: str) -> Optional[str]:
        """Extract province name from question"""
        import re
        
        # Check for specific province names FIRST (more reliable)
        provinces = ['กรุงเทพมหานคร', 'กรุงเทพ', 'กทม', 'เชียงใหม่', 'เชียงราย', 'ขอนแก่น', 
                     'นครราชสีมา', 'ชลบุรี', 'ภูเก็ต', 'สงขลา', 'อุบลราชธานี', 'กระบี่', 
                     'สุราษฎร์ธานี', 'นครศรีธรรมราช', 'สมุทรปราการ', 'นนทบุรี', 'ปทุมธานี']
        for p in provinces:
            if p in question:
                # Return normalized version
                if p in ['กรุงเทพ', 'กทม']:
                    return 'กรุงเทพมหานคร'
                return p
        
        # Pattern: จังหวัด[ชื่อ] - stop at keywords like มี, มีกี่, อยู่, etc.
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
        pattern = r'(?:ระหว่าง|เปรียบเทียบ)\s*(?:โรงเรียน)?([ก-๙a-zA-Z\s]+?)(?:กับ|และ)\s*(?:โรงเรียน)?([ก-๙a-zA-Z\s]+?)(?:$|\s)'
        match = re.search(pattern, question)
        if match:
            return (match.group(1).strip(), match.group(2).strip())
        
        return ("", "")
    
    def _generate_response(self, question: str, results: List[Dict]) -> str:
        """Use LLM to generate natural language response from tool results"""
        
        # Format results for LLM
        data_str = json.dumps(results, ensure_ascii=False, indent=2)
        
        prompt = RESPONSE_GENERATION_PROMPT.format(
            data=data_str,
            question=question
        )
        
        try:
            response = self.llm.generate_content(prompt, timeout=20)
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"❌ Response generation failed: {e}")
            # Fallback: format data nicely
            return self._format_fallback_response(results)
    
    def _format_fallback_response(self, results: List[Dict]) -> str:
        """Fallback response formatting when LLM fails"""
        response = "📊 **สรุปข้อมูลจากการค้นหา:**\n\n"
        
        for result in results:
            tool = result.get("tool", "unknown")
            
            if tool == "count_teachers":
                total = result.get("total_teachers", 0)
                by_gender = result.get("by_gender", {})
                response += f"👨‍🏫 **จำนวนครู:** {total:,} คน\n"
                if by_gender:
                    response += f"• ชาย: {by_gender.get('male', 0):,} คน\n"
                    response += f"• หญิง: {by_gender.get('female', 0):,} คน\n"
                    
            elif tool == "count_students":
                total = result.get("total_students", 0)
                by_gender = result.get("by_gender", {})
                response += f"🎓 **จำนวนนักเรียน:** {total:,} คน\n"
                if by_gender:
                    response += f"• ชาย: {by_gender.get('male', 0):,} คน\n"
                    response += f"• หญิง: {by_gender.get('female', 0):,} คน\n"
                    
            elif tool == "count_schools":
                total = result.get("total_schools", 0)
                response += f"🏫 **จำนวนโรงเรียน:** {total:,} แห่ง\n"
                by_agency = result.get("by_agency", {})
                if by_agency:
                    response += "\n**แยกตามสังกัด:**\n"
                    for agency, count in list(by_agency.items())[:5]:
                        response += f"• {agency}: {count:,} แห่ง\n"
                        
            elif tool == "search_schools" or tool == "list_schools":
                schools = result.get("schools", [])
                if schools:
                    response += "🏫 **รายชื่อโรงเรียน:**\n"
                    for s in schools[:10]:
                        response += f"• {s.get('name', 'ไม่ระบุ')}"
                        if s.get('province'):
                            response += f" ({s['province']})"
                        response += "\n"
                        
            elif tool == "ranking":
                ranking = result.get("ranking", [])
                order_text = "มากที่สุด" if result.get("order") == "most" else "น้อยที่สุด"
                metric_text = "นักเรียน" if result.get("metric") == "students" else "ครู"
                response += f"📈 **อันดับ{metric_text}{order_text}:**\n"
                for item in ranking:
                    response += f"{item['rank']}. {item['name']}: {item['count']:,} คน\n"
                    
            elif tool == "get_ratio":
                ratios = result.get("ratios", [])
                if ratios:
                    response += "📐 **อัตราส่วนนักเรียนต่อครู:**\n"
                    for r in ratios[:5]:
                        school = r.get("school_name", "ไม่ระบุ")
                        ratio = r.get("ratio", 0)
                        students = r.get("students", 0)
                        teachers = r.get("teachers", 0)
                        response += f"• {school}: **{ratio:.1f}:1** ({students:,} นักเรียน / {teachers:,} ครู)\n"
                else:
                    response += "📐 ไม่พบข้อมูลอัตราส่วนสำหรับโรงเรียนที่ค้นหา\n"
                    
            elif tool == "compare":
                e1 = result.get("entity1", {})
                e2 = result.get("entity2", {})
                metric = result.get("metric", "")
                response += f"📊 **เปรียบเทียบ{' จำนวนครู' if metric == 'teachers' else ' จำนวนนักเรียน'}:**\n"
                
                # Extract actual data
                if e1.get("data"):
                    d1 = e1["data"]
                    count1 = d1.get("total_teachers", d1.get("total_students", 0))
                    response += f"• {e1.get('name', 'A')}: {count1:,} คน\n"
                else:
                    response += f"• {e1.get('name', 'A')}: ไม่พบข้อมูล\n"
                    
                if e2.get("data"):
                    d2 = e2["data"]
                    count2 = d2.get("total_teachers", d2.get("total_students", 0))
                    response += f"• {e2.get('name', 'B')}: {count2:,} คน\n"
                else:
                    response += f"• {e2.get('name', 'B')}: ไม่พบข้อมูล\n"
        
        response += "\nครับ"
        return response
    
    def _fallback_response(self, question: str) -> str:
        """Response when no tools were selected - use LLM for general chat"""
        try:
            # Use LLM to generate a natural conversational response
            prompt = f"""คุณคือ น้องดีโอ (DO AI) เป็น AI Assistant ฉลาดและเป็นมิตรจากกระทรวงศึกษาธิการประเทศไทย
            
คุณเชี่ยวชาญด้านข้อมูลการศึกษา เช่น โรงเรียน ครู นักเรียน แต่คุณก็สามารถคุยเล่น พูดคุยทั่วไปได้

ข้อความจากผู้ใช้: "{question}"

กรุณาตอบกลับอย่างเป็นมิตร เป็นธรรมชาติ ใช้ภาษาไทยและใส่ emoji ได้บ้าง
ถ้าเป็นคำถามทักทาย ให้ทักทายกลับ
ถ้าเป็นคำถามทั่วไป ให้ตอบตามความเหมาะสม
ถ้าไม่แน่ใจ สามารถแนะนำให้ถามเกี่ยวกับข้อมูลการศึกษาได้

ตอบสั้นๆ กระชับ ไม่เกิน 3-4 บรรทัด"""

            response = self.llm.generate_content(prompt, timeout=20)
            if response and response.text:
                return response.text
            
        except Exception as e:
            logger.warning(f"⚠️ Fallback LLM failed: {e}")
        
        # Ultimate fallback if LLM also fails
        return (
            "😊 สวัสดีครับ! ผมคือน้องดีโอ พร้อมช่วยเหลือครับ\n\n"
            "💡 ผมเชี่ยวชาญเรื่องข้อมูลการศึกษา ลองถามได้เลยครับ เช่น:\n"
            "• \"กรุงเทพมีโรงเรียนกี่แห่ง\"\n"
            "• \"จำนวนครูในกรุงเทพ\"\n"
        )
    
    def _error_response(self, error: str) -> str:
        """Response when an error occurs"""
        return (
            "😅 ขออภัยครับ เกิดข้อผิดพลาดในการประมวลผล\n\n"
            "💡 กรุณาลองใหม่อีกครั้ง หรือถามคำถามในรูปแบบอื่นครับ"
        )
