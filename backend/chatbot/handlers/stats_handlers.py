"""
Stats Handlers Mixin
Contains handlers for student, teacher, ratio, ranking, and education area queries

📄 ชื่อไฟล์: stats_handlers.py
📝 คำอธิบาย:
   Mixin class ที่รวม handlers เกี่ยวกับสถิติการศึกษา:
   - _handle_student_count_query: นับจำนวนนักเรียน
   - _handle_teacher_count_query: นับจำนวนครู
   - _handle_school_info_v5: ข้อมูลโรงเรียน
   - _handle_ratio_query: อัตราส่วนครู/นักเรียน
   - _handle_school_count_by_area: นับโรงเรียนตามพื้นที่
   - _handle_school_list_by_area: รายชื่อโรงเรียนตามพื้นที่
   - _handle_school_by_agency: โรงเรียนตามสังกัด
   - _handle_ranking_query: จัดอันดับโรงเรียน
   - _handle_education_area_query: ข้อมูลเขตพื้นที่การศึกษา
"""

import re
import logging
from typing import Optional
from ..constants import COLLECTION_NAMES

logger = logging.getLogger(__name__)


class StatsHandlersMixin:
    """
    Mixin class containing statistics-related handler methods.
    Will be mixed into EducationChatbot class.
    
    Requires: self.qdrant_client, self.search_engine, self._format_response_with_llm
    """

    def _handle_student_count_query(self, parsed, message: str) -> Optional[str]:
        """
        🎓 Handle student count queries with grade level and/or gender filters
        Queries edu_students_v5 collection for accurate student statistics
        """
        query_lower = message.lower()
        
        grade_patterns = {
            'ม.1': 'มัธยมศึกษาปีที่ 1', 'ม.2': 'มัธยมศึกษาปีที่ 2', 'ม.3': 'มัธยมศึกษาปีที่ 3',
            'ม.4': 'มัธยมศึกษาปีที่ 4', 'ม.5': 'มัธยมศึกษาปีที่ 5', 'ม.6': 'มัธยมศึกษาปีที่ 6',
            'ป.1': 'ประถมศึกษาปีที่ 1', 'ป.2': 'ประถมศึกษาปีที่ 2', 'ป.3': 'ประถมศึกษาปีที่ 3',
            'ป.4': 'ประถมศึกษาปีที่ 4', 'ป.5': 'ประถมศึกษาปีที่ 5', 'ป.6': 'ประถมศึกษาปีที่ 6',
            'อนุบาล 1': 'อนุบาล 1', 'อนุบาล 2': 'อนุบาล 2', 'อนุบาล 3': 'อนุบาล 3',
        }
        
        gender_keywords = {
            'เพศชาย': 'ชาย', 'เพศหญิง': 'หญิง', 'นักเรียนชาย': 'ชาย', 'นักเรียนหญิง': 'หญิง',
            'ชาย': 'ชาย', 'หญิง': 'หญิง'
        }
        
        detected_grade = None
        for short, full in grade_patterns.items():
            if short.lower() in query_lower:
                detected_grade = short
                break
        
        detected_gender = None
        for keyword, gender_value in gender_keywords.items():
            if keyword in query_lower:
                detected_gender = gender_value
                break
        
        if not detected_grade and not detected_gender:
            return None
        
        # Try to detect school name via Regex (Always run this to catch "Name Number" patterns that LLM might miss)
        # 1. Match "โรงเรียน" prefix
        regex_name = None
        match_prefix = re.search(r'โรงเรียน(.+?)(?=\s+(?:มี|กี่|ชั้น|ที่|ใน|จังหวัด|อำเภอ|$))', message)
        if match_prefix:
            regex_name = match_prefix.group(1).strip()
        
        # 2. Match patterns like "ราชประชานุเคราะห์ 40" (Thai + Number)
        if not regex_name:
            match_num = re.search(r'([ก-๙]+\s*\d+)', message)
            if match_num:
                candidate = match_num.group(1).strip()
                if len(candidate) > 5 and not candidate.startswith(('ชั้น', 'ม.', 'ป.')):
                    regex_name = candidate
        
        # Decide whether to use Regex name or LLM name
        if regex_name:
            if not school_name:
                school_name = regex_name
                logger.info(f"🏫 Used Regex school name: '{school_name}'")
            elif len(regex_name) > len(school_name) and any(c.isdigit() for c in regex_name) and not any(c.isdigit() for c in school_name):
                 # Override if Regex found numbers but LLM didn't (e.g. LLM="ราชประชานุเคราะห์", Regex="ราชประชานุเคราะห์ 40")
                 logger.info(f"⚠️ Overriding LLM name '{school_name}' with Regex name '{regex_name}'")
                 school_name = regex_name

        logger.info(f"🎓 Student Query: grade={detected_grade}, gender={detected_gender}, school={school_name}")
        
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchText
            
            conditions = []
            
            clean_school_name = school_name
            if school_name:
                for prefix in ['โรงเรียน', 'ร.ร.', 'รร.', 'รร']:
                    if school_name.startswith(prefix):
                        clean_school_name = school_name[len(prefix):].strip()
                        break
                logger.info(f"🏫 Clean school name: '{school_name}' → '{clean_school_name}'")
            
            # Prioritize Exact Match (MatchValue)
            if clean_school_name:
                conditions_exact = list(conditions) # Copy base conditions (gender, province...)
                conditions_exact.append(FieldCondition(key="metadata.school_name", match=MatchValue(value=clean_school_name)))
                
                scroll_filter_exact = Filter(must=conditions_exact)
                response_exact = self.qdrant_client.scroll(
                    collection_name="edu_students_v5",
                    scroll_filter=scroll_filter_exact,
                    limit=500,
                    with_payload=True
                )
                if response_exact[0]:
                    logger.info(f"🎯 Found exact match for school: {clean_school_name}")
                    results = response_exact[0]
                else:
                    # Fallback to Partial Match (MatchText)
                    # Note: MatchText can be too loose, so we might want to restrict it or check results
                    conditions.append(FieldCondition(key="metadata.school_name", match=MatchText(text=clean_school_name)))
                    
                    scroll_filter = Filter(must=conditions) if conditions else None
                    response = self.qdrant_client.scroll(
                        collection_name="edu_students_v5",
                        scroll_filter=scroll_filter,
                        limit=500,
                        with_payload=True
                    )
                    results = response[0]
            else:
                 # No school name, use base conditions
                 scroll_filter = Filter(must=conditions) if conditions else None
                 response = self.qdrant_client.scroll(
                    collection_name="edu_students_v5",
                    scroll_filter=scroll_filter,
                    limit=500,
                    with_payload=True
                )
                 results = response[0]
            
            if not results:
                logger.info(f"⚠️ No exact match, trying semantic search...")
                search_query = f"โรงเรียน{school_name or ''} {detected_grade or ''} {detected_gender or ''} {parsed.agency or ''}"
                results = self.search_engine._semantic_search(search_query, "edu_students_v5", top_k=50)
            
            if detected_grade and results:
                grade_lower = detected_grade.lower()
                filtered_results = []
                for r in results:
                    meta = r.payload.get('metadata', {})
                    grade_in_data = meta.get('grade', '').lower()
                    if grade_lower in grade_in_data or grade_patterns.get(detected_grade, '').lower() in grade_in_data:
                        filtered_results.append(r)
                results = filtered_results
            
            logger.info(f"📊 Found {len(results)} student records")
            
            if results:
                school_counts = {}
                for r in results:
                    meta = r.payload.get('metadata', {})
                    # DEBUG: Add school name debug tag
                    school = meta.get('school_name', 'ไม่ระบุ')
                    school = f"{school} [Q: {school_name}]" 
                    count = meta.get('count', 1)
                    
                    if school not in school_counts:
                        school_counts[school] = {
                            'total': 0,
                            'province': meta.get('province'),
                            'district': meta.get('district'),
                            'grade': meta.get('grade'),
                            'gender': meta.get('gender')
                        }
                    school_counts[school]['total'] += count
                
                total_students = sum(s['total'] for s in school_counts.values())
                
                data = {
                    "school_counts": {k: v for k, v in school_counts.items()},
                    "total_students": total_students,
                    "detected_grade": detected_grade,
                    "detected_gender": detected_gender,
                    "school_name": school_name,
                    "num_schools": len(school_counts)
                }
                
                return self._format_response_with_llm(message, data, "student_count")
            else:
                response_text = f"❌ ไม่พบข้อมูลนักเรียน"
                if school_name:
                    response_text += f" โรงเรียน \"{school_name}\""
                if detected_grade:
                    response_text += f" ระดับ {detected_grade}"
                if detected_gender:
                    response_text += f" เพศ{detected_gender}"
                response_text += "\n\n💡 **แนะนำ:**\n• ตรวจสอบชื่อโรงเรียนให้ถูกต้อง\n• ลองค้นหาด้วยชื่อเต็มหรือชื่อย่อ\n"
                return response_text
                
        except Exception as e:
            logger.error(f"❌ Student count query error: {e}")
            return None

    def _handle_teacher_count_query(self, parsed, message: str) -> Optional[str]:
        """
        👨‍🏫 Handle teacher count queries
        Queries edu_teachers_v5 collection for accurate teacher statistics
        """
        query_lower = message.lower()
        
        teacher_keywords = ['ครู', 'อาจารย์', 'บุคลากร', 'teacher', 'คุณครู', 
                           'ข้าราชการ', 'พนักงานราชการ', 'ลูกจ้าง']
        
        has_teacher_keyword = any(kw in query_lower for kw in teacher_keywords)
        
        if not has_teacher_keyword:
            return None
        
        gender_keywords = {
            'เพศชาย': 'ชาย', 'เพศหญิง': 'หญิง', 
            'ครูชาย': 'ชาย', 'ครูหญิง': 'หญิง',
            'ชาย': 'ชาย', 'หญิง': 'หญิง'
        }
        
        detected_gender = None
        for keyword, gender_value in gender_keywords.items():
            if keyword in query_lower:
                detected_gender = gender_value
                break
        
        school_name = parsed.school_name
        if not school_name:
            patterns = [r'โรงเรียน([^\s]+)', r'ร\.ร\.([^\s]+)', r'รร\.([^\s]+)']
            for pattern in patterns:
                match = re.search(pattern, message)
                if match:
                    school_name = match.group(1).strip()
                    for suffix in ['ครับ', 'ค่ะ', 'มี', 'ที่', 'ใน']:
                        if school_name.endswith(suffix):
                            school_name = school_name[:-len(suffix)]
                    break
        
        clean_school_name = school_name
        if school_name:
            for prefix in ['โรงเรียน', 'ร.ร.', 'รร.', 'รร']:
                if school_name.startswith(prefix):
                    clean_school_name = school_name[len(prefix):].strip()
                    break
        
        logger.info(f"👨‍🏫 Teacher Query: gender={detected_gender}, school={clean_school_name}")
        
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchText
            
            conditions = []
            
            if clean_school_name:
                conditions.append(FieldCondition(key="metadata.school_name", match=MatchText(text=clean_school_name)))
            
            if parsed.province:
                conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=parsed.province)))
            
            if detected_gender:
                conditions.append(FieldCondition(key="metadata.gender", match=MatchValue(value=detected_gender)))
            
            scroll_filter = Filter(must=conditions) if conditions else None
            
            response = self.qdrant_client.scroll(
                collection_name="edu_teachers_v5",
                scroll_filter=scroll_filter,
                limit=500,
                with_payload=True
            )
            
            results = response[0]
            
            if not results and clean_school_name:
                logger.info(f"⚠️ No exact match for teachers, trying semantic search...")
                search_query = f"ครูโรงเรียน{clean_school_name}"
                results = self.search_engine._semantic_search(search_query, "edu_teachers_v5", top_k=50)
            
            logger.info(f"📊 Found {len(results)} teacher records")
            
            if results:
                school_counts = {}
                for r in results:
                    meta = r.payload.get('metadata', {})
                    school = meta.get('school_name', 'ไม่ระบุ')
                    count = meta.get('count', 1)
                    gender = meta.get('gender', '-')
                    
                    if school not in school_counts:
                        school_counts[school] = {
                            'total': 0,
                            'male': 0,
                            'female': 0,
                            'province': meta.get('province')
                        }
                    school_counts[school]['total'] += count
                    if gender == 'ชาย':
                        school_counts[school]['male'] += count
                    elif gender == 'หญิง':
                        school_counts[school]['female'] += count
                
                total_teachers = sum(s['total'] for s in school_counts.values())
                
                data = {
                    "school_counts": {k: v for k, v in school_counts.items()},
                    "total_teachers": total_teachers,
                    "detected_gender": detected_gender,
                    "school_name": clean_school_name,
                    "num_schools": len(school_counts)
                }
                
                return self._format_response_with_llm(message, data, "teacher_count")
            else:
                response_text = f"❌ ไม่พบข้อมูลครู"
                if clean_school_name:
                    response_text += f" โรงเรียน \"{clean_school_name}\""
                if detected_gender:
                    response_text += f" เพศ{detected_gender}"
                response_text += "\n\n💡 ลองตรวจสอบชื่อโรงเรียนให้ถูกต้อง"
                return response_text
                
        except Exception as e:
            logger.error(f"❌ Teacher count query error: {e}")
            return None

    def _handle_school_info_v5(self, parsed, message: str) -> Optional[str]:
        """
        🏫 Handle school info queries from school collection
        Returns detailed school information including address, agency, students, teachers
        """
        query_lower = message.lower()
        
        info_keywords = ['ข้อมูล', 'รายละเอียด', 'ที่อยู่', 'ที่ตั้ง', 'อยู่ที่ไหน', 'สังกัด', 
                         'เบอร์โทร', 'โทรศัพท์', 'ติดต่อ', 'มีนักเรียนกี่คน', 'มีนักเรียนทั้งหมด']
        
        has_info_keyword = any(kw in query_lower for kw in info_keywords)
        
        school_name = parsed.school_name
        if not school_name:
            patterns = [r'โรงเรียน([^\s]+)', r'ร\.ร\.([^\s]+)', r'รร\.([^\s]+)']
            for pattern in patterns:
                match = re.search(pattern, message)
                if match:
                    school_name = match.group(1).strip()
                    for suffix in ['ครับ', 'ค่ะ', 'มี', 'ที่', 'ใน', 'อยู่']:
                        if school_name.endswith(suffix):
                            school_name = school_name[:-len(suffix)]
                    break
        
        if not school_name or not has_info_keyword:
            return None
        
        clean_school_name = school_name
        for prefix in ['โรงเรียน', 'ร.ร.', 'รร.', 'รร']:
            if school_name.startswith(prefix):
                clean_school_name = school_name[len(prefix):].strip()
                break
        
        logger.info(f"🏫 School Info V5 Query: school={clean_school_name}")
        
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            import json
            
            response = self.qdrant_client.scroll(
                collection_name="edu_schools_v5",
                scroll_filter=Filter(must=[
                    FieldCondition(key="metadata.school_name", match=MatchValue(value=clean_school_name))
                ]),
                limit=5,
                with_payload=True
            )
            
            results = response[0]
            
            if not results:
                logger.info(f"⚠️ No exact match in school collection, trying semantic...")
                results = self.search_engine._semantic_search(f"โรงเรียน{clean_school_name}", COLLECTION_NAMES["schools"], top_k=5)
            
            logger.info(f"📊 Found {len(results)} school records")
            
            if results:
                best = results[0]
                m = best.payload.get('metadata', {})
                
                data = {
                    "school_name": m.get('school_name', clean_school_name),
                    "province": m.get('province'),
                    "district": m.get('district'),
                    "subdistrict": m.get('subdistrict'),
                    "agency": m.get('agency'),
                    "area_name": m.get('area_name'),
                    "total_students": m.get('total_students'),
                    "total_teachers": m.get('total_teachers'),
                    "lat": m.get('lat'),
                    "lon": m.get('lon')
                }
                
                response_text = self._format_response_with_llm(message, data, "school_info")
                
                if m.get('lat') and m.get('lon'):
                    address = f"ต.{m.get('subdistrict', '-')} อ.{m.get('district', '-')} จ.{m.get('province', '-')}"
                    map_json = json.dumps({
                        "latitude": float(m.get('lat')),
                        "longitude": float(m.get('lon')),
                        "schoolName": m.get('school_name'),
                        "address": address
                    }, ensure_ascii=False)
                    response_text += f"\n\n<map>{map_json}</map>"
                
                return response_text
            else:
                return f"❌ ไม่พบข้อมูลโรงเรียน \"{clean_school_name}\" ในฐานข้อมูล\n\n💡 ลองตรวจสอบชื่อโรงเรียนให้ถูกต้อง"
                
        except Exception as e:
            logger.error(f"❌ School info v5 error: {e}")
            return None

    def _handle_ratio_query(self, parsed, message: str) -> Optional[str]:
        """
        📊 Handle student-teacher ratio queries from edu_ratios_v5
        """
        query_lower = message.lower()
        
        ratio_keywords = ['อัตราส่วน', 'สัดส่วน', 'ratio', 'ครูต่อนักเรียน', 'นักเรียนต่อครู']
        
        has_ratio_keyword = any(kw in query_lower for kw in ratio_keywords)
        
        if not has_ratio_keyword:
            return None
        
        school_name = parsed.school_name
        if not school_name:
            patterns = [r'โรงเรียน([^\s]+)', r'ร\.ร\.([^\s]+)']
            for pattern in patterns:
                match = re.search(pattern, message)
                if match:
                    school_name = match.group(1).strip()
                    for suffix in ['ครับ', 'ค่ะ', 'มี', 'ที่', 'ใน']:
                        if school_name.endswith(suffix):
                            school_name = school_name[:-len(suffix)]
                    break
        
        clean_school_name = school_name
        if school_name:
            for prefix in ['โรงเรียน', 'ร.ร.', 'รร.', 'รร']:
                if school_name.startswith(prefix):
                    clean_school_name = school_name[len(prefix):].strip()
                    break
        
        logger.info(f"📊 Ratio Query: school={clean_school_name}")
        
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            
            conditions = []
            if clean_school_name:
                conditions.append(FieldCondition(key="metadata.school_name", match=MatchValue(value=clean_school_name)))
            if parsed.province:
                conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=parsed.province)))
            
            scroll_filter = Filter(must=conditions) if conditions else None
            
            response = self.qdrant_client.scroll(
                collection_name="edu_ratios_v5",
                scroll_filter=scroll_filter,
                limit=100,
                with_payload=True
            )
            
            results = response[0]
            
            logger.info(f"📊 Found {len(results)} ratio records")
            
            if results:
                if clean_school_name and len(results) == 1:
                    m = results[0].payload.get('metadata', {})
                    data = {
                        "school_name": m.get('school_name'),
                        "province": m.get('province'),
                        "total_students": m.get('total_students', 0),
                        "total_teachers": m.get('total_teachers', 0),
                        "ratio": m.get('ratio'),
                        "type": "single_school"
                    }
                else:
                    sorted_results = sorted(results, key=lambda x: x.payload.get('metadata', {}).get('ratio', 999))
                    top_schools = []
                    for r in sorted_results[:10]:
                        m = r.payload.get('metadata', {})
                        top_schools.append({
                            "school_name": m.get('school_name'),
                            "ratio": m.get('ratio')
                        })
                    data = {
                        "top_schools": top_schools,
                        "type": "ranking"
                    }
                
                return self._format_response_with_llm(message, data, "ratio")
            else:
                if clean_school_name:
                    return f"❌ ไม่พบข้อมูลอัตราส่วนของโรงเรียน \"{clean_school_name}\""
                else:
                    return f"❌ ไม่พบข้อมูลอัตราส่วน กรุณาระบุโรงเรียนหรือจังหวัด"
                
        except Exception as e:
            logger.error(f"❌ Ratio query error: {e}")
            return None

    def _handle_school_count_by_area(self, parsed, message: str) -> Optional[str]:
        """
        🏫 Handle school count queries by province/district
        Counts schools from school collection collection
        """
        query_lower = message.lower()
        
        count_keywords = ['กี่โรง', 'กี่แห่ง', 'มีโรงเรียน', 'จำนวนโรงเรียน', 'โรงเรียนทั้งหมด', 
                          'เท่าไร', 'เท่าไหร่', 'ในระบบ', 'มีทั้งหมด']
        
        has_count_keyword = any(kw in query_lower for kw in count_keywords)
        
        if not has_count_keyword:
            return None
        
        district = parsed.district
        if not district:
            district_patterns = [r'เขต([^\s]+)', r'อำเภอ([^\s]+)', r'อ\.([^\s]+)']
            for pattern in district_patterns:
                match = re.search(pattern, message)
                if match:
                    district = match.group(1).strip()
                    for suffix in ['ครับ', 'ค่ะ', 'มี', 'มีกี่', 'ใน', 'โรง']:
                        if district.endswith(suffix):
                            district = district[:-len(suffix)]
                    break
        
        province = parsed.province
        if not province:
            bkk_names = ['กรุงเทพ', 'กทม', 'บางกอก', 'กรุงเทพฯ', 'กรุงเทพมหานคร']
            for name in bkk_names:
                if name in message:
                    province = 'กรุงเทพมหานคร'
                    break
        
        if not province and not district and not parsed.region:
            return None
        
        logger.info(f"🏫 School Count by Area: region={parsed.region}, province={province}, district={district}")
        
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchText, MatchAny
            from .constants import REGIONS
            
            conditions = []
            
            if province:
                conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))
            
            if district:
                conditions.append(FieldCondition(key="metadata.district", match=MatchText(text=district)))
                
            if parsed.region and parsed.region in REGIONS:
                provinces_in_region = REGIONS[parsed.region]
                conditions.append(FieldCondition(key="metadata.province", match=MatchAny(any=provinces_in_region)))
            
            scroll_filter = Filter(must=conditions) if conditions else None
            
            all_results = []
            offset = None
            
            while True:
                response = self.qdrant_client.scroll(
                    collection_name=COLLECTION_NAMES["schools"],
                    scroll_filter=scroll_filter,
                    limit=500,
                    offset=offset,
                    with_payload=True
                )
                
                points = response[0]
                next_offset = response[1]
                
                all_results.extend(points)
                
                if next_offset is None or len(points) == 0:
                    break
                offset = next_offset
            
            logger.info(f"📊 Found {len(all_results)} schools in area (province={province}, district={district})")
            
            if all_results:
                agency_counts = {}
                for r in all_results:
                    m = r.payload.get('metadata', {})
                    agency = m.get('agency', 'ไม่ระบุ')
                    if agency not in agency_counts:
                        agency_counts[agency] = 0
                    agency_counts[agency] += 1
                
                total_schools = len(all_results)
                
                data = {
                    "location": {
                        "region": parsed.region,
                        "province": province,
                        "district": district
                    },
                    "counts": {
                        "total": total_schools,
                        "agencies": agency_counts
                    },
                    "sample_schools": []
                }
                
                return self._format_response_with_llm(message, data, "school_count")
            else:
                # Try semantic search fallback
                search_query = f"โรงเรียนใน{parsed.region or province or district}"
                logger.info(f"⚠️ No exact match for school count, trying semantic search: {search_query}")
                results = self.search_engine._semantic_search(search_query, COLLECTION_NAMES["schools"], top_k=50)
                
                if results:
                     # Construct data from semantic results (approximate)
                     data = {
                        "location": {
                            "region": parsed.region,
                            "province": province,
                            "district": district
                        },
                        "counts": {
                            "total": len(results), # This is top_k limited, but better than 0
                            "agencies": {} # Cannot easily aggregate
                        },
                        "sample_schools": [{"name": r.payload.get('metadata', {}).get('school_name')} for r in results[:5]]
                    }
                     return self._format_response_with_llm(message, data, "school_count")
                
                area_name = district or province or parsed.region or "พื้นที่นี้"
                return f"❌ ไม่พบโรงเรียนใน{area_name}\n\n💡 ลองค้นหาพื้นที่อื่น"
                
        except Exception as e:
            logger.error(f"❌ School count by area error: {e}")
            return None

    def _handle_school_list_by_area(self, parsed, message: str) -> Optional[str]:
        """
        📋 Handle school list queries by area
        Returns list of schools in province/district
        """
        query_lower = message.lower()
        
        list_keywords = ['รายชื่อ', 'ชื่อโรงเรียน', 'โรงเรียนทั้งหมด', 'มีโรงเรียนอะไร', 'โรงเรียนอะไรบ้าง']
        
        has_list_keyword = any(kw in query_lower for kw in list_keywords)
        if not has_list_keyword:
            return None
        
        district = parsed.district
        province = parsed.province
        
        if not province:
            bkk_names = ['กรุงเทพ', 'กทม', 'บางกอก']
            for name in bkk_names:
                if name in message:
                    province = 'กรุงเทพมหานคร'
                    break
        
        if not province and not district:
            return None
        
        logger.info(f"📋 School List: province={province}, district={district}")
        
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchText
            
            conditions = []
            if province:
                conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))
            if district:
                conditions.append(FieldCondition(key="metadata.district", match=MatchText(text=district)))
            
            response = self.qdrant_client.scroll(
                collection_name=COLLECTION_NAMES["schools"],
                scroll_filter=Filter(must=conditions) if conditions else None,
                limit=50,
                with_payload=True
            )
            
            results = response[0]
            
            # Get actual total count (not limited)
            try:
                count_result = self.qdrant_client.count(
                    collection_name=COLLECTION_NAMES["schools"],
                    count_filter=Filter(must=conditions) if conditions else None,
                    exact=True
                )
                actual_total = count_result.count
            except Exception as count_error:
                logger.warning(f"Count query failed: {count_error}")
                actual_total = len(results)  # Fallback to scroll count
            
            if results:
                schools_list = []
                for r in results[:20]:
                    m = r.payload.get('metadata', {})
                    schools_list.append({
                        "name": m.get('school_name', '-'),
                        "students": m.get('total_students', 0),
                        "agency": m.get('agency', '-')
                    })
                
                data = {
                    "province": province,
                    "district": district,
                    "total_count": actual_total,  # Actual total in database
                    "total_found": len(schools_list),  # Number displayed (limited)
                    "schools": schools_list
                }
                
                return self._format_response_with_llm(message, data, "school_list")
            else:
                return f"❌ ไม่พบโรงเรียนในพื้นที่นี้"
                
        except Exception as e:
            logger.error(f"❌ School list error: {e}")
            return None

    def _handle_school_by_agency(self, parsed, message: str) -> Optional[str]:
        """
        🏛️ Handle school queries by agency
        Counts/lists schools by agency (สพฐ, สช, กทม, อาชีวะ)
        """
        query_lower = message.lower()
        
        agency_keywords = {
            'สพฐ': 'สำนักงานคณะกรรมการการศึกษาขั้นพื้นฐาน',
            'สพฐ.': 'สำนักงานคณะกรรมการการศึกษาขั้นพื้นฐาน',
            'เอกชน': 'สำนักงานคณะกรรมการส่งเสริมการศึกษาเอกชน',
            'สช': 'สำนักงานคณะกรรมการส่งเสริมการศึกษาเอกชน',
            'สช.': 'สำนักงานคณะกรรมการส่งเสริมการศึกษาเอกชน',
            'กทม': 'สำนักการศึกษา กรุงเทพมหานคร',
            'อาชีวะ': 'สำนักงานคณะกรรมการการอาชีวศึกษา',
            'อาชีวศึกษา': 'สำนักงานคณะกรรมการการอาชีวศึกษา',
        }
        
        detected_agency = None
        agency_display = None
        for keyword, full_name in agency_keywords.items():
            if keyword in query_lower:
                detected_agency = full_name
                agency_display = keyword
                break
        
        if not detected_agency:
            return None
        
        province = parsed.province or 'กรุงเทพมหานคร'
        if 'กรุงเทพ' in message or 'กทม' in message:
            province = 'กรุงเทพมหานคร'
        
        logger.info(f"🏛️ Agency Query: agency={agency_display}, province={province}")
        
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchText
            
            conditions = [
                FieldCondition(key="metadata.agency", match=MatchText(text=detected_agency[:30]))
            ]
            if province:
                conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))
            
            all_results = []
            offset = None
            
            while True:
                response = self.qdrant_client.scroll(
                    collection_name=COLLECTION_NAMES["schools"],
                    scroll_filter=Filter(must=conditions),
                    limit=500,
                    offset=offset,
                    with_payload=True
                )
                all_results.extend(response[0])
                if response[1] is None or len(response[0]) == 0:
                    break
                offset = response[1]
            
            logger.info(f"📊 Found {len(all_results)} schools by agency")
            
            if all_results:
                sorted_results = sorted(all_results, key=lambda x: x.payload.get('metadata', {}).get('total_students', 0), reverse=True)
                top_schools = []
                for r in sorted_results[:10]:
                    m = r.payload.get('metadata', {})
                    top_schools.append({
                        "school_name": m.get('school_name'),
                        "total_students": m.get('total_students', 0)
                    })
                
                data = {
                    "agency": agency_display,
                    "province": province,
                    "total_count": len(all_results),
                    "schools": top_schools
                }
                
                return self._format_response_with_llm(message, data, "agency")
            else:
                return f"❌ ไม่พบโรงเรียนสังกัด{agency_display}"
                
        except Exception as e:
            logger.error(f"❌ Agency query error: {e}")
            return None

    def _handle_ranking_query(self, parsed, message: str) -> Optional[str]:
        """
        🏆 Handle ranking queries
        Finds top/bottom schools by students, teachers, ratio
        """
        query_lower = message.lower()
        
        ranking_keywords_max = ['มากที่สุด', 'มากสุด', 'ใหญ่ที่สุด', 'ใหญ่สุด', 'อันดับ 1', 'top']
        ranking_keywords_min = ['น้อยที่สุด', 'น้อยสุด', 'เล็กที่สุด', 'เล็กสุด']
        
        is_max = any(kw in query_lower for kw in ranking_keywords_max)
        is_min = any(kw in query_lower for kw in ranking_keywords_min)
        
        if not is_max and not is_min:
            return None
        
        is_student = 'นักเรียน' in query_lower or 'นร' in query_lower
        is_teacher = 'ครู' in query_lower or 'อาจารย์' in query_lower
        
        if not is_student and not is_teacher:
            is_student = True
        
        province = parsed.province or 'กรุงเทพมหานคร'
        if 'กรุงเทพ' in message or 'กทม' in message:
            province = 'กรุงเทพมหานคร'
        
        metric = 'total_students' if is_student else 'total_teachers'
        metric_name = 'นักเรียน' if is_student else 'ครู'
        
        logger.info(f"🏆 Ranking Query: metric={metric}, max={is_max}, province={province}")
        
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            
            all_results = []
            offset = None
            
            conditions = []
            if province:
                conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))
            if parsed.agency:
                conditions.append(FieldCondition(key="metadata.agency", match=MatchText(text=parsed.agency)))
            
            while True:
                response = self.qdrant_client.scroll(
                    collection_name=COLLECTION_NAMES["schools"],
                    scroll_filter=Filter(must=conditions) if conditions else None,
                    limit=500,
                    offset=offset,
                    with_payload=True
                )
                all_results.extend(response[0])
                if response[1] is None or len(response[0]) == 0:
                    break
                offset = response[1]
            
            sorted_results = sorted(
                all_results, 
                key=lambda x: x.payload.get('metadata', {}).get(metric, 0), 
                reverse=is_max
            )
            
            logger.info(f"📊 Found {len(sorted_results)} schools for ranking")
            
            if sorted_results:
                top_schools = []
                for r in sorted_results[:10]:
                    m = r.payload.get('metadata', {})
                    top_schools.append({
                        "school_name": m.get('school_name'),
                        "value": m.get(metric, 0)
                    })
                
                data = {
                    "province": province,
                    "metric": metric_name,
                    "is_max": is_max,
                    "order": "มากที่สุด" if is_max else "น้อยที่สุด",
                    "schools": top_schools
                }
                
                return self._format_response_with_llm(message, data, "ranking")
            else:
                return f"❌ ไม่พบข้อมูลโรงเรียน"
                
        except Exception as e:
            logger.error(f"❌ Ranking query error: {e}")
            return None

    def _handle_education_area_query(self, parsed, message: str) -> Optional[str]:
        """
        📌 Handle education area queries
        Queries edu_areas_v5 for สพม., สพป. info
        """
        area_keywords = ['สพม', 'สพป', 'เขตพื้นที่การศึกษา', 'เขตพื้นที่']
        
        has_area_keyword = any(kw in message for kw in area_keywords)
        if not has_area_keyword:
            return None
        
        area_match = re.search(r'(สพม\.?|สพป\.?)\s*([^\s]+)', message)
        area_name = None
        if area_match:
            prefix = area_match.group(1)
            suffix = area_match.group(2)
            area_name = f"{prefix}{suffix}"
        
        logger.info(f"📌 Education Area Query: area_name={area_name}")
        
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchText
            
            conditions = []
            if area_name:
                conditions.append(FieldCondition(key="metadata.area_name", match=MatchText(text=area_name)))
            
            response = self.qdrant_client.scroll(
                collection_name="edu_areas_v5",
                scroll_filter=Filter(must=conditions) if conditions else None,
                limit=10,
                with_payload=True
            )
            
            results = response[0]
            
            if results:
                response_text = f"📌 **ข้อมูลเขตพื้นที่การศึกษา**\n\n"
                
                for r in results[:5]:
                    m = r.payload.get('metadata', {})
                    response_text += f"🏫 **{m.get('area_name', '-')}**\n"
                    if m.get('school_count'):
                        response_text += f"   📊 จำนวนโรงเรียน: {m.get('school_count'):,} แห่ง\n"
                    if m.get('provinces'):
                        response_text += f"   📍 ครอบคลุม: {m.get('provinces')}\n"
                    response_text += "\n"
                
                return response_text
            else:
                response2 = self.qdrant_client.scroll(
                    collection_name=COLLECTION_NAMES["schools"],
                    scroll_filter=Filter(must=[FieldCondition(key="metadata.area_name", match=MatchText(text=area_name or "สพม"))]),
                    limit=100,
                    with_payload=True
                )
                
                schools = response2[0]
                if schools:
                    total = len(schools)
                    response_text = f"📌 **{area_name or 'เขตพื้นที่การศึกษา'}**\n\n"
                    response_text += f"📊 พบ {total} โรงเรียนในเขตนี้\n\n"
                    
                    for i, r in enumerate(schools[:5], 1):
                        m = r.payload.get('metadata', {})
                        response_text += f"{i}. {m.get('school_name')}\n"
                    
                    return response_text
                else:
                    return f"❌ ไม่พบข้อมูลเขต{area_name or 'พื้นที่นี้'}"
                
        except Exception as e:
            logger.error(f"❌ Education area query error: {e}")
            return None
