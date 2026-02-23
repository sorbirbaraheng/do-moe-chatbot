"""ResponseGeneratorMixin - LLM response generation + fallback formatting."""
import json
import logging
import re
from typing import Dict, Any, List, Optional
from ..tools import RESPONSE_GENERATION_PROMPT
logger = logging.getLogger(__name__)

class ResponseGeneratorMixin:

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
