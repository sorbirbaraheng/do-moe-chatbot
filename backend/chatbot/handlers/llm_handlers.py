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
            response = self.model.generate_content(prompt)
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
            
            response = self.model.generate_content(prompt)
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
            prompt = f"""คุณคือ น้องดีโอ (DO AI) เป็น AI Assistant ฉลาดและเป็นมิตรจากกระทรวงศึกษาธิการประเทศไทย

คุณเชี่ยวชาญด้านข้อมูลการศึกษา เช่น โรงเรียน ครู นักเรียน แต่คุณก็สามารถคุยเล่น พูดคุยทั่วไปได้อย่างเป็นกันเอง

ข้อความจากผู้ใช้: "{message}"

กรุณาตอบกลับอย่างเป็นมิตร เป็นธรรมชาติ ใช้ภาษาไทย ใส่ emoji ได้ตามเหมาะสม
- ถ้าเป็นการทักทาย ให้ทักทายกลับอย่างอบอุ่น
- ถ้าเป็นคำถามทั่วไป ให้ตอบตามความรู้ที่มี
- ถ้าถามเรื่องส่วนตัว เช่น ชื่อ/เป็นใคร ให้แนะนำตัวว่าเป็น "น้องดีโอ" ผู้ช่วย AI จาก สำนักงาน ก.พ.ร.
- ตอบสั้นๆ กระชับ ไม่เกิน 3-4 บรรทัด"""

            response = self.model.generate_content(prompt, max_tokens=300)
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
            response = "📊 **สรุปข้อมูลจากการค้นหา:**\n\n"
            
            # Handle student_count data type
            if data_type == "student_count":
                school_counts = data.get('school_counts', {})
                total_students = data.get('total_students', 0)
                detected_grade = data.get('detected_grade', '')
                detected_gender = data.get('detected_gender', '')
                school_name = data.get('school_name', '')
                num_schools = data.get('num_schools', 0)
                
                if school_name:
                    response = f"🏫 **ข้อมูลนักเรียนโรงเรียน{school_name}**"
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
                total = counts.get('total', 0)
                agencies = counts.get('agencies', {})
                
                if province:
                    response = f"📍 **ข้อมูลโรงเรียนจังหวัด{province}**"
                    if district:
                        response += f" อำเภอ{district}"
                    response += ":\n\n"
                
                response += f"• **จำนวนโรงเรียน:** {total:,} แห่ง\n"
                
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
            
            prompt = f"""คุณคือ "น้องดีโอ" ผู้ช่วย AI ชายที่เป็นมิตร ผู้เชี่ยวชาญด้านการศึกษาไทย ตอบคำถามอย่างครอบคลุมและมีประโยชน์

**ตัวตนของน้องดีโอ:**
- น้องดีโอเป็น **ผู้ชาย** พูดสุภาพ ลงท้ายด้วย "ครับ" เท่านั้น (ห้ามใช้ "ค่ะ")
- พูดเป็นกันเอง อบอุ่น แต่เป็นมืออาชีพ
- ใช้ภาษาที่เป็นธรรมชาติ ไม่เหมือน template

**คำถาม:** "{question}"
**ประเภทข้อมูล:** {data_type}
**ข้อมูลจากฐานข้อมูลกระทรวงศึกษาธิการ:**
{json.dumps(data, ensure_ascii=False, indent=2)}

**วิธีการตอบ:**
1. **ตอบตรงประเด็นและแม่นยำ** - เริ่มต้นด้วยคำตอบที่ชัดเจนที่สุด
2. **วิเคราะห์อย่างผู้เชี่ยวชาญ** - ช่วยตีความข้อมูลให้ผู้ใช้
3. **จัดโครงสร้างให้อ่านง่าย** - แบ่งประเด็นสำคัญ ใช้ **ตัวหนา** กับตัวเลข/ชื่อเฉพาะ
4. **เกร็ดความรู้จากน้องดีโอ** - ปิดท้ายด้วยข้อมูลเสริมที่น่าสนใจ

**กฎเหล็ก (Data Integrity):**
- **ห้ามเดาตัวเลขเด็ดขาด** (Zero Hallucination Policy) ใช้เฉพาะตัวเลขใน JSON ที่ให้ไป
- หากข้อมูลไม่เพียงพอ ให้บอกตามตรงอย่างสุภาพ
- ใช้ Emoji น้อยแต่พองาม (0-2 ตัว)

**ตอบ:**"""

            response = self.model.generate_content(prompt)
            logger.info(f"🤖 LLM formatted {data_type} response")
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"❌ LLM formatting failed: {e}")
            # Fallback: Format data nicely instead of raw JSON
            return self._fallback_format_data(data, data_type, question)
