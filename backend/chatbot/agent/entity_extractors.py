"""
🔍 EntityExtractorMixin – Regex-based entity extraction from user queries.
Extracts school names, provinces, regions, genders, grades, agencies,
person types, districts, comparison entities, thresholds, and years.
"""

import logging
import re
from typing import Dict, Any, Optional

from ..core.constants import THAI_PROVINCES, PROVINCE_ALIASES, REGIONS

logger = logging.getLogger(__name__)


class EntityExtractorMixin:
    """Regex-based entity extraction helpers used by tool selection and enrichment."""

    def _extract_school_name(self, question: str) -> Optional[str]:
        """Extract school name from question using patterns - Enhanced for Name+Number"""
        # ============================================================
        # PRIORITY ORDER: Most specific patterns first!
        # ============================================================

        # 1. Match "โรงเรียน[Name]" with stop words
        match = re.search(r'โรงเรียน(.+?)(?=\s*(?:อยู่|มี|กี่|ชั้น|ที่|ใน|จังหวัด|อำเภอ|สังกัด|ครู|นักเรียน|ระดับ|แห่ง|คน|รายชื่อ|เฉพาะ|ตำแหน่ง|หน่อย|ครับ|ค่ะ|นะ|บ้าง|$))', question)
        if match:
            school = match.group(1).strip()
            bad_tokens = [
                'การสอน', 'การเรียน', 'การศึกษา', 'อะไรบ้าง', 'อย่างไร', 'ไหม',
                'ที่มี', 'ซึ่ง', 'ทั้งหมด', 'กี่', 'ใด', 'นี้', 'นั้น', 'โน้น',
                'สพฐ', 'สช', 'อปท', 'ตชด', 'กทม', 'เอกชน', 'ในระบบ', 'นอกระบบ',
                'นักเรียน', 'ครู', 'บุคลากร', 'คน', 'แห่ง', 'มากกว่า', 'น้อยกว่า',
                'ไม่เกิน', 'ต่ำกว่า', 'อย่างน้อย', 'ที่นักเรียน', 'ที่ครู',
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
        match_num = re.search(r'([ก-๙]+\s+\d+)', question)
        if match_num:
            candidate = match_num.group(1).strip()
            bad_num_tokens = ['นักเรียน', 'ครู', 'คน', 'แห่ง', 'มากกว่า', 'น้อยกว่า', 'ไม่เกิน', 'ต่ำกว่า', 'อย่างน้อย']
            if candidate.startswith("ที่") or any(x in candidate for x in bad_num_tokens):
                logger.info(f"🏫 Ignoring false positive school name (num pattern): '{candidate}'")
                return None
            if len(candidate) > 5 and not re.match(r'^[มป]\s*\d', candidate):
                logger.info(f"🏫 Extracted school (name+number pattern): '{candidate}'")
                return candidate

        # 2.5 Match "Thai Name + จังหวัด" pattern
        match_before_province = re.search(r'^([ก-๙a-zA-Z]+)(?:\s+(?:จังหวัด|จ\.))', question)
        if match_before_province:
            candidate = match_before_province.group(1).strip()
            from ..core.thai_provinces import THAI_PROVINCES as _TP
            if candidate not in _TP and len(candidate) > 2:
                logger.info(f"🏫 Extracted school (before-province pattern): '{candidate}'")
                return candidate

        # 3. Famous school name keywords
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

        # 3.5 Institution prefix patterns (ศูนย์, สถาบัน, กศน, etc.)
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
        stop_words = r'(?=\s*(?:มี|กี่|ชั้น|ที่|ใน|จังหวัด|อำเภอ|สังกัด|ครู|นักเรียน|ระดับ|หน่อย|ครับ|ค่ะ|นะ|บ้าง|$))'
        patterns = [
            r'โรงเรียน([ก-๙a-zA-Z\s]+)' + stop_words,
            r'รร\.([ก-๙a-zA-Z\s]+)' + stop_words,
            r'รร\s+([ก-๙a-zA-Z\s]+)' + stop_words,
            r'วิทยาลัย([ก-๙a-zA-Z\s]+)' + stop_words,
            r'(?:วิทยาลัย)?เทคนิค([ก-๙a-zA-Z\s]+?)' + stop_words,
            r'(?:วัด|บ้าน|ชุมชน|อนุบาล|เทศบาล)\s*([ก-๙a-zA-Z0-9\s]+)' + stop_words,
        ]
        for pattern in patterns:
            match = re.search(pattern, question)
            if match:
                school = match.group(1).strip()
                for suffix in ['มี', 'กี่', 'ชั้น', 'นักเรียน', 'ครู', 'แห่ง', 'คน']:
                    if school.endswith(suffix):
                        school = school[:-len(suffix)].strip()
                if len(school) > 2 and school not in ['กี่แห่ง', 'กี่คน', 'อะไรบ้าง', 'อย่างไร', 'ทั้งหมด']:
                    logger.info(f"🏫 Extracted school (fallback pattern): '{school}'")
                    return school

        return None

    def _extract_province(self, question: str) -> Optional[str]:
        """Extract province name from question using THAI_PROVINCES constant"""
        placeholder_words = {"ไหน", "ใด", "อะไร", "ไหนบ้าง", "ทั้งหมด", "เท่าไหร่", "กี่แห่ง", "กี่โรง"}

        for alias, full_name in PROVINCE_ALIASES.items():
            if alias in question:
                return full_name

        sorted_provinces = sorted(THAI_PROVINCES, key=len, reverse=True)
        for p in sorted_provinces:
            if p in question:
                if p == "เลย" and "เลย" in question:
                    if "จังหวัดเลย" in question or "เมืองเลย" in question:
                        return p
                    continue
                return p

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
        region_aliases = {
            "อีสาน": "ภาคตะวันออกเฉียงเหนือ",
            "ภาคอีสาน": "ภาคตะวันออกเฉียงเหนือ",
            "ตะวันออกเฉียงเหนือ": "ภาคตะวันออกเฉียงเหนือ",
        }
        for alias, full in region_aliases.items():
            if alias in question:
                return full

        for region in REGIONS.keys():
            if region in question:
                return region

        return None

    def _extract_gender(self, question: str) -> Optional[str]:
        """Extract gender from question"""
        female_keywords = ['เพศหญิง', 'ผู้หญิง', 'หญิง', 'สตรี']
        for kw in female_keywords:
            if kw in question:
                return 'หญิง'

        male_keywords = ['เพศชาย', 'ผู้ชาย', 'ชาย']
        for kw in male_keywords:
            if kw in question:
                return 'ชาย'

        return None

    def _extract_grade(self, question: str) -> Optional[str]:
        """Extract grade level from question (ม.2, ป.6, etc.)"""
        grade_patterns = [
            (r'ม\.?\s*(\d)', 'ม.'),
            (r'มัธยม\s*(\d)', 'ม.'),
            (r'ป\.?\s*(\d)', 'ป.'),
            (r'ประถม\s*(\d)', 'ป.'),
            (r'ชั้น\s*ม\.?\s*(\d)', 'ม.'),
            (r'ชั้น\s*ป\.?\s*(\d)', 'ป.'),
            (r'อนุบาล\s*(\d)?', 'อนุบาล'),
            (r'ปวช\.?\s*(\d)', 'ปวช.'),
            (r'ปวส\.?\s*(\d)', 'ปวส.'),
            (r'ประกาศนียบัตรวิชาชีพชั้นสูง\s*ปีที่\s*(\d)', 'ปวส.'),
            (r'ประกาศนียบัตรวิชาชีพ\s*ปีที่\s*(\d)', 'ปวช.'),
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
        placeholder_words = {"ไหน", "ใด", "อะไร", "ไหนบ้าง", "ทั้งหมด", "เท่าไหร่", "กี่แห่ง", "กี่โรง"}

        match = re.search(r'อำเภอ\s*(เมือง[ก-๙]+?)(?=มี|มีกี่|อยู่|ที่|ใน|$|\s)', question)
        if match:
            return match.group(1).strip()

        match = re.search(r'อำเภอ\s*([ก-๙]+?)(?=มี|มีกี่|อยู่|ที่|ใน|$|\s)', question)
        if match:
            district = match.group(1).strip()
            if district in placeholder_words or district.startswith(("ไหน", "ใด", "อะไร")):
                return None
            if district == "เมือง":
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

        pattern = r'เขต([ก-๙]+)'
        match = re.search(pattern, question)
        if match:
            district = match.group(1).strip()
            for d in bangkok_districts:
                if d in district or district in d:
                    return d
            return district

        for d in bangkok_districts:
            if d in question:
                return d

        return None

    def _extract_comparison_entities(self, question: str) -> tuple:
        """Extract two entities from comparison question"""
        pattern = r'(?:ระหว่าง|เปรียบเทียบ|เทียบ)\s*(?:โรงเรียน)?([ก-๙a-zA-Z\s]+?)(?:กับ|และ)\s*(?:โรงเรียน)?([ก-๙a-zA-Z\s]+?)(?:$|\s)'
        match = re.search(pattern, question)
        return ("", "")

    def _extract_threshold_followup(self, text: str) -> Dict[str, Any]:
        """Extract numeric threshold/operator from a short follow-up like 'มากกว่า 1500 คน'."""
        if not text:
            return {"value": None, "operator": None}
        thai_to_arabic = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
        normalized = text.translate(thai_to_arabic)
        value = None
        operator = None

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
        thai_to_arabic = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
        normalized = text.translate(thai_to_arabic)

        match = re.search(r'(\d{4})', normalized)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                return None
        match2 = re.search(r'(\d{2})', normalized)
        if match2 and ("ปี" in normalized or "พ.ศ" in normalized or "พศ" in normalized):
            try:
                return 2500 + int(match2.group(1))
            except Exception:
                return None
        return None
