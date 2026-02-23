"""
LLM Handlers Mixin
Contains LLM-related methods: intent classification, RAG fallback, response formatting

📄 ชื่อไฟล์: llm_handlers.py
📝 คำอธิบาย:
   Mixin class ที่รวม methods เกี่ยวกับ LLM:
   - _classify_intent_with_llm: จำแนกเจตนาของผู้ใช้
   - _rag_fallback: ใช้ RAG เมื่อไม่เจอข้อมูล
   - _generate_general_response: สร้างคำตอบทั่วไป
   - _fallback_format_data: จัดรูปแบบข้อมูลเมื่อ LLM ล้ม
   - _format_response_with_llm: ใช้ LLM จัดรูปแบบคำตอบ
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class LLMHandlersMixin:
    """
    Mixin class containing LLM-related handler methods.
    Will be mixed into EducationChatbot class.
    
    Requires: self.model, self.collections, self.search_engine
    """

    def _classify_intent_with_llm(self, query: str) -> str:
        """Use LLM to classify query intent: 'GENERAL' or 'EDUCATION'"""
        try:
            if len(query) < 4:
                return "GENERAL"
                
            prompt = f"""
            Classify this query into one category:
            1. GENERAL: Greetings, small talk, asking "who are you", "what can you do", "eating?", "where are you going?", jokes, weather, generic questions NOT related to education.
            2. EDUCATION: Questions about schools, students, teachers, stats, locations, rankings, comparisons, finding schools, educational data.
            
            Query: "{query}"
            
            Return ONLY the word "GENERAL" or "EDUCATION".
            """
            response = self.model.generate_content(prompt, timeout=10)
            return response.text.strip().upper()
        except Exception as e:
            logger.error(f"LLM Classification failed: {e}")
            return "EDUCATION"

    def _rag_fallback(self, query: str) -> str:
        """Universal Fallback: Use RAG to answer unstructured queries"""
        try:
            intent_type = self._classify_intent_with_llm(query)
            current_category = getattr(self, '_current_category', 'general')
            
            # UNIFIED MODE: Simply log and let LLM Agent handle all queries
            if "GENERAL" in intent_type and current_category in ['school', 'student']:
                logger.info(f"🌐 General intent detected in school/student category - LLM Agent will handle")
            
            logger.info(f"🧠 RAG Fallback: Searching context for '{query}'...")
            
            context_items = []
            
            # Search Schools
            if 'schools' in self.collections:
                schools = self.search_engine._semantic_search(query, self.collections['schools'], top_k=3)
                for s in schools:
                    m = s.payload.get('metadata', {})
                    context_items.append(f"School: {m.get('school_name')} (จ.{m.get('province')}) - สังกัด: {m.get('agency')}")
                    
            # Search Province Stats
            if 'province' in self.collections:
                stats = self.search_engine._semantic_search(query, self.collections['province'], top_k=3)
                for s in stats:
                    m = s.payload.get('metadata', {})
                    context_items.append(f"Stat (จ.{m.get('province')}): {m.get('total_schools')} Schools, {m.get('total_teachers')} Teachers")

            context_str = "\n".join(context_items)
            
            prompt = f"""
            Role: You are DO-MOE (น้องดีโอ), a friendly education assistant from Thailand's Ministry of Education.
            Goal: Answer the user's question using the provided context.
            
            Context from Database:
            {context_str}
            
            User Question: "{query}"
            
            Instructions:
            - Answer naturally in Thai with a friendly tone.
            - If context contains the answer, use it.
            - If you cannot answer from context, apologize politely and offer to help with other education questions.
            - Be helpful, friendly, and speak as "น้องดีโอ".
            """
            
            response = self.model.generate_content(prompt, timeout=30)
            return response.text
            
        except Exception as e:
            logger.error(f"RAG Fallback failed: {e}")
            return (
                "😊 ขออภัยครับ น้องดีโอไม่พบข้อมูลที่ตรงกับคำถามนี้ในฐานข้อมูลครับ\n\n"
                "💡 ลองถามด้วยคำถามอื่น หรือระบุชื่อโรงเรียน/จังหวัดให้ชัดเจนนะครับ ✨"
            )

    def _generate_general_response(self, message: str) -> str:
        """
        🌐 Generate direct LLM response for general/casual queries
        No database lookup needed - pure conversational AI
        """
        try:
            prompt = f"""คุณคือ "น้องดีโอ" (DO AI) ผู้ช่วย AI อารมณ์ดีจากกระทรวงศึกษาธิการ
            
            **บุคลิกภาพ (สำคัญมาก):**
            - 👦 **เป็นผู้ชายเท่านั้น** ใช้คำลงท้าย "ครับ" เสมอ (ห้ามใช้ "คะ/ค่ะ" เด็ดขาด)
            - 🤝 **พูดคุยเป็นธรรมชาติ** เหมือนเพื่อนคุยกับเพื่อน ไม่เป็นทางการเกินไป
            - 🚫 **ห้ามขึ้นต้นด้วย "สวัสดีครับ"** (ยกเว้นเป็นการทักทายครั้งแรกจริงๆ) ให้เข้าเรื่องทันที
            - 🙅‍♂️ **ห้ามใช้คำว่า "สวัสดีครับ/ค่ะ"** (ห้ามมี /ค่ะ เด็ดขาด)
            
            **สถานการณ์:**
            ผู้ใช้กำลังสนทนากับคุณ (ข้อความด้านล่าง)
            
            **ข้อควรระวัง:**
            - ถ้าระบบ Database พัง ให้บอกว่า "ตอนนี้ผมตอบได้แค่เรื่องทั่วไปนะครับ พอดีระบบข้อมูลโรงเรียนกำลังปรับปรุงอยู่ครับ"
            - ห้ามแนะนำให้กดเมนู 3 ขีด หรือแนะนำโหมดอื่น (เพราะไม่มี)
            
            ข้อความจากผู้ใช้: "{message}"
            
            ตอบกลับสั้นๆ กระชับ (ไม่เกิน 2-3 บรรทัด):"""

            response = self.model.generate_content(prompt, max_tokens=300, timeout=15)
            if response and hasattr(response, 'text') and response.text:
                logger.info(f"✅ General response generated successfully")
                return response.text
            
            # Alternative: try getting response directly
            if response and isinstance(response, str):
                return response
                
        except Exception as e:
            logger.warning(f"⚠️ General LLM response failed: {e}")
        
        # Static fallback if LLM fails
        return (
            "😊 สวัสดีครับ! ผมคือน้องดีโอ พร้อมช่วยเหลือครับ\n\n"
            "💡 ผมเชี่ยวชาญเรื่องข้อมูลการศึกษา ลองถามได้เลยครับ เช่น:\n"
            "• \"กรุงเทพมีโรงเรียนกี่แห่ง\"\n"
            "• \"จำนวนครูในกรุงเทพ\"\n"
        )

    def _fallback_format_data(self, data: dict, data_type: str, question: str) -> str:
        """
        📝 Fallback formatter when LLM fails
        Formats data nicely instead of returning raw JSON
        """
        try:
            response = ""
            
            # Handle student_count data type
            if data_type == "student_count":
                school_counts = data.get('school_counts', {})
                total_students = data.get('total_students', 0)
                detected_grade = data.get('detected_grade', '')
                detected_gender = data.get('detected_gender', '')
                school_name = data.get('school_name', '')
                num_schools = data.get('num_schools', 0)
                
                if school_name:
                    response = f"สวัสดีครับพี่! น้องดีโอเช็คข้อมูลมาให้แล้วครับ 👦✨\n\n"
                    response += f"🏫 **ข้อมูลนักเรียนโรงเรียน{school_name}**"
                    if detected_grade:
                        response += f" ระดับ **{detected_grade}**"
                    if detected_gender:
                        response += f" เพศ **{detected_gender}**"
                    response += ":\n\n"
                
                for idx, (school, info) in enumerate(list(school_counts.items())[:10], 1):
                    total = info.get('total', 0)
                    province = info.get('province', '')
                    district = info.get('district', '')
                    grade = info.get('grade', '')
                    
                    response += f"**{idx}. {school}**\n"
                    response += f"• จำนวน: **{total:,}** คน\n"
                    if province:
                        response += f"• จังหวัด: {province}\n"
                    if district:
                        response += f"• อำเภอ/เขต: {district}\n"
                    if grade:
                        response += f"• ระดับชั้น: {grade}\n"
                    response += "\n"
                
                response += f"\n📈 **รวมทั้งหมด:** {total_students:,} คน"
                if num_schools > 1:
                    response += f" ใน {num_schools} โรงเรียน"
                response += "ครับ"
                
            # Handle teacher_count data type
            elif data_type == "teacher_count":
                school_counts = data.get('school_counts', {})
                total_teachers = data.get('total_teachers', 0)
                
                response = f"สวัสดีครับพี่! น้องดีโอเช็คข้อมูลครูมาให้แล้วครับ 👨‍🏫✨\n\n"
                
                for idx, (school, info) in enumerate(list(school_counts.items())[:10], 1):
                    total = info.get('total', 0)
                    response += f"**{idx}. {school}**\n"
                    response += f"• จำนวนครู: **{total:,}** คน\n\n"
                
                response += f"\n📈 **รวมทั้งหมด:** {total_teachers:,} คนครับ"
                
            # Handle school_count data type
            elif data_type == "school_count":
                location = data.get('location', {})
                counts = data.get('counts', {})
                sample_schools = data.get('sample_schools', [])
                
                province = location.get('province', '')
                district = location.get('district', '')
                region = location.get('region', '')
                total = counts.get('total', 0)
                agencies = counts.get('agencies', {})
                
                response = f"สวัสดีครับพี่! น้องดีโอนับจำนวนโรงเรียนให้แล้วครับ 🏫✨\n\n"
                
                if region:
                    response += f"📍 **พื้นที่{region}**"
                elif province:
                    response += f"📍 **พื้นที่จังหวัด{province}**"
                
                if district:
                    response += f" อำเภอ{district}"
                
                if region or province or district:
                    response += ":\n\n"
                
                response += f"• **ทั้งหมด:** {total:,} แห่ง\n"
                
                if agencies:
                    response += "\n**แยกตามสังกัด:**\n"
                    for agency, count in agencies.items():
                        response += f"• {agency}: **{count:,}** แห่ง\n"
                
                if sample_schools:
                    response += "\n**ตัวอย่างโรงเรียน:**\n"
                    for school in sample_schools[:5]:
                        name = school.get('name', 'ไม่ระบุ')
                        response += f"• {name}\n"
                
                response += "\nครับ"
                
            # Handle student_count_not_found data type
            elif data_type == "student_count_not_found":
                school_name = data.get('school_name', '')
                requested = data.get('requested_grade', '')
                available = data.get('available_grades', {})
                total = data.get('total_students', 0)
                response = f"โรงเรียน{school_name} ไม่ได้เปิดสอนชั้น {requested} ครับ"
                if available:
                    levels = ', '.join(available.keys())
                    response += f"\n\n🏢 โรงเรียนนี้เปิดสอน: **{levels}**"
                    response += f"\n📊 นักเรียนทั้งหมด: **{total:,} คน**ครับ"
                response += f"\n\n💡 ลองถามระดับที่มีได้ เช่นลองถาม '{list(available.keys())[0] if available else 'ป.1'} มีกี่คน'"
                return response
            # Generic fallback
            else:
                # Just format key-value pairs nicely
                for key, value in data.items():
                    if isinstance(value, dict):
                        response += f"**{key}:**\n"
                        for k, v in list(value.items())[:5]:
                            if isinstance(v, (int, float)):
                                response += f"• {k}: **{v:,}**\n"
                            else:
                                response += f"• {k}: {v}\n"
                    elif isinstance(value, (int, float)):
                        response += f"• **{key}:** {value:,}\n"
                    elif isinstance(value, str):
                        response += f"• **{key}:** {value}\n"
                response += "\nครับ"
            
            return response
            
        except Exception as e:
            logger.error(f"❌ Fallback format failed: {e}")
            # Ultimate fallback - still better than raw JSON
            return "😊 ได้รับข้อมูลจากระบบแล้วครับ กรุณาลองถามใหม่อีกครั้งนะครับ"

    def _format_response_with_llm(self, question: str, data: dict, data_type: str) -> str:
        """
        🤖 Use LLM to format response naturally based on context
        """
        try:
            import json

            # Build data_type-specific instruction
            extra_instructions = ""
            if data_type == "student_count_not_found":
                extra_instructions = """
**กรณีพิเศษ: ไม่พบชั้นเรียนที่ถาม** (grade_not_found = true)
1. อธิบายอย่างเป็นอารมณ์ดีว่าโรงเรียนนี้ไม่ได้เปิดสอนระดับชั้นที่ถาม
2. บอกว่าโรงเรียนนี้เปิดสอนระดับใดบ้าง (จาก available_grades) และมีนักเรียนรวมเท่าไร (total_students)
3. เสนอทางเลือกให้ปิ่ เช่น "ปิ่อยากทราบว่าชั้น ป.X มีกี่คนไหมครับ"
4. ห้ามใช้ ❌ หรือบอกว่า"ไม่พบข้อมูล" ตรงๆ ให้พูดเป็นธรรมชาติว่าโรงเรียนเปิดกี่ระดับ"""

            prompt = f"""คุณคือ "น้องดีโอ" (DO-MOE) ผู้ช่วย AI อารมณ์ดีจากกระทรวงศึกษาธิการ
หน้าที่ของคุณคือรายงานข้อมูลการศึกษาให้เข้าใจง่ายและน่าอ่านที่สุด

**บุคลิกของน้องดีโอ:**
- 👦 **เป็นผู้ชาย** สุภาพ อ่อนน้อม (ใช้ "ครับ" เสมอ)
- 🤝 **เป็นกันเอง** เหมือนน้องรายงานพี่ (ใช้คำว่า "พี่" แทนผู้ใช้ได้)
- 💡 **ฉลาดและกระตือรือร้น** ที่จะช่วยเหลือ
{extra_instructions}
**คำถามจากพี่:** "{question}"
**ข้อมูลที่พบ:**
{json.dumps(data, ensure_ascii=False, indent=2)}

**คำแนะนำการตอบ:**
1. **ทักทายอย่างสดใส** (เช่น "สวัสดีครับพี่! น้องดีโอไปค้นข้อมูลมาให้แล้วครับ/เจอข้อมูลแล้วครับ")
2. **สรุปคำตอบให้ชัดเจน** ในบรรทัดแรก
3. **แสดงรายละเอียด** เป็นข้อย่อยอ่านง่าย (ใช้ Emoji ประกอบหัวข้อ)
4. **ปิดท้าย** ด้วยเกร็ดเล็กๆ หรือชวนถามต่อ

**ข้อควรระวัง:**
- ห้ามมั่วตัวเลขเด็ดขาด (ใช้ตามที่ให้เท่านั้น)
- ถ้าข้อมูลเป็น 0 หรือหาไม่เจอ ให้ตอบขอโทษอย่างจริงใจและแนะนำให้ลองค้นใหม่

**เริ่มตอบ:**"""

            response = self.model.generate_content(prompt, timeout=30)
            logger.info(f"🤖 LLM formatted {data_type} response")
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"❌ LLM formatting failed: {e}")
            # Fallback: Format data nicely instead of raw JSON
            return self._fallback_format_data(data, data_type, question)

