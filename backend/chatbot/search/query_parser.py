"""
Smart Query Parser for Education Chatbot
Handles intent detection, entity extraction, and query normalization
"""

import re
import logging
from typing import Dict, Optional, Any

from ..core.types import QueryIntent, QueryLevel, ParsedQuery
from ..core.constants import (
    THAI_PROVINCES, PROVINCE_ALIASES, REGIONS, AGENCY_ALIASES, POPULAR_DISTRICTS
)
from ..core.llm import MultiProviderLLM
from .location_lookup import LocationLookup, get_location_lookup

logger = logging.getLogger(__name__)


# =====================================================================
# INTENT DETECTION KEYWORDS
# =====================================================================
INTENT_KEYWORDS = {
    QueryIntent.RANKING_MOST: [
        'มากที่สุด', 'เยอะที่สุด', 'สูงสุด', 'มากสุด', 'เยอะสุด', 
        'ที่สุด', 'อันดับ 1', 'อันดับหนึ่ง', 'อันดับแรก', 'top'
    ],
    QueryIntent.RANKING_LEAST: [
        'น้อยที่สุด', 'น้อยสุด', 'ต่ำสุด', 'ต่ำที่สุด',
        'อันดับท้าย', 'อันดับสุดท้าย', 'รั้งท้าย'
    ],
    QueryIntent.COMPARE: [
        'เปรียบเทียบ', 'เทียบ', 'เทียบกับ', 'vs', 'versus',
        'แตกต่าง', 'ต่างกัน'
    ],
    # Threshold filters (match patterns like "น้อยกว่า 50 แห่ง", "มากกว่า 100 โรง")
    QueryIntent.FILTER_LESS_THAN: [
        'น้อยกว่า', 'ต่ำกว่า', 'ไม่เกิน', 'ไม่ถึง', 'ต่ำว่า'
    ],
    QueryIntent.FILTER_GREATER_THAN: [
        'มากกว่า', 'เกินกว่า', 'เกิน', 'สูงกว่า', 'มากว่า'
    ],
    QueryIntent.FILTER_EQUALS: [
        'เท่ากับ', 'พอดี', 'เท่ากัน', 'ตรง'
    ],
    QueryIntent.COUNT: [
        'มีกี่', 'กี่โรง', 'กี่แห่ง', 'จำนวน', 'เท่าไหร่', 'เท่าไร',
        'รวมทั้งหมด', 'ทั้งหมด', 'รวมกัน'
    ],
    QueryIntent.LIST: [
        'แสดงรายชื่อ', 'รายชื่อ', 'ลิสต์', 'list', 'แสดงทั้งหมด',
        'มีอะไรบ้าง', 'อะไรบ้าง'
    ],
    QueryIntent.SCHOOL_SEARCH: [
        'หาโรงเรียน', 'ค้นหาโรงเรียน', 'โรงเรียน', 'ร.ร.', 'รร.',
        'โรงเรียนไหน', 'โรงเรียนอะไร'
    ],
    QueryIntent.SCHOOL_LIST: [
        'โรงเรียนใน', 'รายชื่อโรงเรียน', 'โรงเรียนทั้งหมดใน',
        'โรงเรียนที่อยู่ใน', 'โรงเรียนสังกัด'
    ],
    QueryIntent.SCHOOL_DETAIL: [
        'ข้อมูลโรงเรียน', 'รายละเอียดโรงเรียน', 'เบอร์โทรโรงเรียน',
        'ที่อยู่โรงเรียน', 'ติดต่อโรงเรียน', 'อยู่ที่ไหน', 'อยู่ตรงไหน',
        'ขอข้อมูล', 'ขอรายละเอียด'
    ],
    QueryIntent.SCHOOL_COUNT: [
        'โรงเรียนกี่แห่ง', 'มีโรงเรียนกี่', 'จำนวนโรงเรียน',
        'โรงเรียนทั้งหมดกี่', 'กี่โรง', 'กี่โรงเรียน', 'มีโรงเรียน',
        'โรงเรียนเท่าไหร่', 'มีกี่โรงเรียน', 'โรงเรียนมีกี่'
    ],
    QueryIntent.LOAD_MORE: [
        'ดูเพิ่มเติม', 'ดูต่อ', 'ดูเพิ่ม', 'ขอดูต่อ', 'ขอดูเพิ่ม',
        'แสดงเพิ่ม', 'แสดงต่อ', 'หน้าถัดไป', 'ถัดไป', 'เพิ่มเติม',
        'ขอเพิ่ม', 'load more', 'more', 'next'
    ]
}


class LLMIntentClassifier:
    """Uses LLM to classify user intent intelligently"""
    
    CLASSIFICATION_PROMPT = '''คุณเป็น AI จำแนกประเภทคำถามเกี่ยวกับการศึกษาไทย
ตอบเป็น JSON เท่านั้น ห้ามมีข้อความอื่น

ประเภทคำถาม (intent):
- SCHOOL_COUNT: ถามจำนวนโรงเรียน เช่น "มีกี่โรง", "กี่โรงเรียน", "จำนวนเท่าไหร่"
- STUDENT_COUNT: ถามจำนวนนักเรียน เช่น "มีนักเรียนกี่คน", "นักเรียนชายกี่คน", "นักเรียน ม.6 กี่คน"
- TEACHER_COUNT: ถามจำนวนครู เช่น "มีครูกี่คน", "ครูผู้หญิงกี่คน", "จำนวนครู"
- RATIO: ถามอัตราส่วนครูต่อนักเรียน
- SCHOOL_LIST: ขอรายชื่อโรงเรียน เช่น "รายชื่อโรงเรียน", "โรงเรียนใน", "มีโรงเรียนอะไรบ้าง"
- SCHOOL_DETAIL: ขอข้อมูลโรงเรียนเฉพาะ เช่น "ข้อมูลโรงเรียน...", "โรงเรียน...อยู่ที่ไหน", "เบอร์โทรโรงเรียน..."
- SCHOOL_SEARCH: ค้นหาโรงเรียนจากชื่อบางส่วน เช่น "หาโรงเรียน...", "ค้นหาโรงเรียน..."
- FILTER_LESS_THAN: กรองข้อมูลที่น้อยกว่าจำนวนที่กำหนด เช่น "อำเภอที่มีโรงเรียนน้อยกว่า 40", "จังหวัดที่มีน้อยกว่า 100 โรง"
- FILTER_GREATER_THAN: กรองข้อมูลที่มากกว่าจำนวนที่กำหนด เช่น "อำเภอที่มีโรงเรียนมากกว่า 50", "เกิน 100 โรง"
- COMPARE: เปรียบเทียบข้อมูล 2 จังหวัดขึ้นไป เช่น "เปรียบเทียบปัตตานีกับยะลา", "ระหว่าง...กับ..."
- RANKING_MOST: อันดับมากที่สุด เช่น "จังหวัดไหนมีมากที่สุด", "อันดับ 1"
- RANKING_LEAST: อันดับน้อยที่สุด เช่น "จังหวัดไหนมีน้อยที่สุด"
- LOAD_MORE: ดูเพิ่ม เช่น "ดูเพิ่มเติม", "ดูต่อ", "ถัดไป"
- GENERAL: คำถามทั่วไปที่ไม่เข้าข้างต้น

หมายเหตุ FILTER:
- ถ้าคำถามมี "น้อยกว่า", "ต่ำกว่า", "ไม่เกิน" → ใช้ FILTER_LESS_THAN
- ถ้าคำถามมี "มากกว่า", "เกินกว่า", "เกิน", "สูงกว่า" → ใช้ FILTER_GREATER_THAN
- ต้องมี threshold (ตัวเลข) ถึงจะเป็น FILTER เช่น "น้อยกว่า 40", "เกิน 100"

ภูมิภาคที่รองรับ: ภาคเหนือ, ภาคใต้, ภาคกลาง, ภาคตะวันออก, ภาคตะวันตก, ภาคตะวันออกเฉียงเหนือ, ภาคอีสาน

**คำย่อสังกัดที่สำคัญ** (ต้องแปลงให้ถูกต้อง):
- สพฐ, สพฐ. = สำนักงานคณะกรรมการการศึกษาขั้นพื้นฐาน
- สช, สช., เอกชน = สำนักงานคณะกรรมการส่งเสริมการศึกษาเอกชน
- อปท, อปท., ท้องถิ่น = กรมส่งเสริมการปกครองท้องถิ่น
- สอศ, สอศ., อาชีวะ = สำนักงานคณะกรรมการการอาชีวศึกษา
- กศน, กศน. = กรมส่งเสริมการเรียนรู้
- ตชด, ตชด. = กองบัญชาการตำรวจตระเวนชายแดน


หมายเหตุ สถานที่:
- ถ้ามี "ตำบล", "แขวง", "ต." → ใส่ชื่อตำบลใน subdistrict
- ถ้ามี "อำเภอ", "เขต", "อ." → ใส่ชื่ออำเภอใน district  
- ถ้ามี "จังหวัด", "จ." → ใส่ชื่อจังหวัดใน province

**การดึงชื่อโรงเรียน (School Extraction):**
- ให้ดึงชื่อเฉพาะออกมา แม้ไม่มีคำนำหน้า "โรงเรียน"
- ตัวอย่าง: "ราชประชานุเคราะห์ 40" -> school_name: "ราชประชานุเคราะห์ 40"
- ตัวอย่าง: "เตรียมอุดม" -> school_name: "เตรียมอุดม"
- ตัวอย่าง: "เทพศิรินทร์" -> school_name: "เทพศิรินทร์"

ตอบ JSON:
{"intent": "...", "region": "..." หรือ null, "province": "..." หรือ null, "district": "..." หรือ null, "subdistrict": "..." หรือ null, "agency": "..." หรือ null, "school_name": "..." หรือ null, "threshold": ตัวเลข หรือ null}

คำถาม: '''

    def __init__(self, model=None):
        self.model = model
        self.llm = MultiProviderLLM(category="school")
        
    def classify(self, query: str) -> dict:
        """Classify user intent using LLM (Groq primary, Gemini fallback)"""
        import json
        try:
            prompt = self.CLASSIFICATION_PROMPT + query
            
            llm_response = self.llm.generate_content(prompt, timeout=10)
            result_text = llm_response.text if llm_response else None
            
            if result_text:
                # Clean up response - extract JSON
                if '```json' in result_text:
                    result_text = result_text.split('```json')[1].split('```')[0].strip()
                elif '```' in result_text:
                    result_text = result_text.split('```')[1].split('```')[0].strip()
                
                result = json.loads(result_text)
                
                # Normalize agency
                agency = result.get('agency')
                if agency:
                    agency = AGENCY_ALIASES.get(agency, agency)
                    result['agency'] = agency
                
                logger.info(f"🧠 LLM Intent: {result}")
                return result
                
        except Exception as e:
            logger.warning(f"⚠️ LLM classification failed: {e}")
            
        return None


class ResponseSynthesizer:
    """Generates comprehensive, ChatGPT-quality responses from database results"""
    
    SYNTHESIS_PROMPT = '''คุณคือ "น้องดีโอ" ผู้ช่วย AI ด้านการศึกษาไทย

🎭 **บุคลิก**: พูดเป็นกันเอง สุภาพ ใช้ "ครับ" (เป็นผู้ชาย)

💬 **วิธีตอบ**:
- ตอบเหมือนคนคุยกันจริงๆ ไม่ใช่หุ่นยนต์
- เข้าใจสิ่งที่ผู้ใช้ถาม แล้วตอบตรงประเด็น
- ถ้าเป็นคำถามต่อเนื่อง ให้เชื่อมโยงกับบริบทก่อนหน้า
- ใช้ภาษาไทยธรรมชาติ หลากหลาย ไม่ซ้ำซาก

⚠️ **กฎที่ต้องปฏิบัติอย่างเคร่งครัด**:
1. ตัวเลขทุกตัวต้องมาจาก "ข้อมูล" ที่ให้มาเท่านั้น ห้ามแต่งเอง
2. ถ้าข้อมูลมี agency_breakdown หรือ agencies → **ต้องแสดงตัวเลขแยกตามสังกัดทั้งหมด**
3. ถ้าข้อมูลมี sample_schools → แสดงตัวอย่าง 3-5 โรงเรียน

📊 **รูปแบบการตอบ (บังคับ)**:

ถ้าถามจำนวนโรงเรียน:
"[พื้นที่] มีโรงเรียนทั้งหมด **XX แห่ง** ครับ 🏫

**แยกตามสังกัด:**
• สพฐ. xxx แห่ง
• สช./เอกชน xxx แห่ง
• อปท./ท้องถิ่น xxx แห่ง
• กทม. xxx แห่ง
• อาชีวะ xxx แห่ง
[แสดงทุกสังกัดที่มีในข้อมูล]

**ตัวอย่างโรงเรียน:**
• [ชื่อโรงเรียน 1]
• [ชื่อโรงเรียน 2]
• [ชื่อโรงเรียน 3]"

ถ้าถามเปรียบเทียบ:
"เปรียบเทียบแล้ว [พื้นที่ 1] มี โรงเรียน XX แห่ง ส่วน [พื้นที่ 2] มี YY แห่ง..."

**กฎเหล็ก**: 
1. 🚫 **ห้ามใช้ภาษาจีน (Chinese), ญี่ปุ่น (Japanese) หรือเกาหลี (Korean) เด็ดขาด** 
2. 🚫 **ห้ามเติมคำว่า "学校" หรืออักษรต่างประเทศใดๆ ในชื่อโรงเรียน**
3. ใช้ภาษาไทยเป็นหลักเท่านั้น (ยกเว้นคำทับศัพท์ที่จำเป็น)

ถ้าเป็นการค้นหาแบบละเอียด (ADVANCED_SEARCH):
"🔍 **ผลการค้นหา** [สรุปเงื่อนไขสั้นๆ] พบทั้งหมด **XX แห่ง** ครับ

**รายชื่อโรงเรียน:**
1. **[ชื่อโรงเรียน]** ([ตำบล/อำเภอ])
   - 👥 นักเรียน: [จำนวน] คน | 👨‍🏫 ครู: [จำนวน] คน
   - 🏢 สังกัด: [ชื่อเขตพื้นที่/สังกัด]
   - 📍 [ทำลิงก์ Google Maps ถ้ามี lat,lon]
2. [โรงเรียนที่ 2]... "

**ห้าม**: ตอบแค่ตัวเลขรวมโดยไม่แยกตามสังกัด (ถ้าข้อมูลมี breakdown อยู่)

ข้อมูล:
'''


    def __init__(self):
        self.llm = MultiProviderLLM(category="school")

    def synthesize(self, intent: str, data: dict, query: str) -> str:
        """Generate comprehensive response using LLM"""
        import json
        import re as regex
        try:
            context = f"คำถามผู้ใช้: {query}\n"
            context += f"ประเภทคำถาม: {intent}\n"
            context += f"ข้อมูล:\n{json.dumps(data, ensure_ascii=False, indent=2)}\n"
            
            # DEBUG: Log the data being sent
            logger.info(f"🤖 Synthesize data: counts={data.get('counts', {})}, samples={len(data.get('sample_schools', []))}")
            
            prompt = self.SYNTHESIS_PROMPT + context
            
            llm_response = self.llm.generate_content(prompt, timeout=30)
            result = llm_response.text if llm_response else None
            
            # DEBUG: Log first 200 chars of LLM response
            if result:
                logger.info(f"🤖 LLM response preview: {result[:200]}...")
            
            if result:
                # Post-process: Collapse multiple newlines into max 2
                result = regex.sub(r'\n{3,}', '\n\n', result)
                # Collapse double newlines between bullet points
                result = regex.sub(r'(\* .+)\n\n(\* )', r'\1\n\2', result)
                result = regex.sub(r'(• .+)\n\n(• )', r'\1\n\2', result)
                result = regex.sub(r'(\d+\. .+)\n\n(\d+\. )', r'\1\n\2', result)
                
                logger.info(f"✨ Response synthesized successfully")
                return result
                
        except Exception as e:
            logger.warning(f"⚠️ Response synthesis failed: {e}")
            
        return None


class SmartQueryParser:
    """Production-Ready Smart Query Parser with LLM Intelligence"""
    
    def __init__(self, qdrant_client=None):
        self._province_cache = {p.lower(): p for p in THAI_PROVINCES}
        self._alias_cache = {k.lower(): v for k, v in PROVINCE_ALIASES.items()}
        self.llm_classifier = LLMIntentClassifier()
        self.llm = MultiProviderLLM(category="school")
        
        # Initialize LocationLookup for fuzzy province/district matching
        self.location_lookup = None
        if qdrant_client:
            self.location_lookup = get_location_lookup(qdrant_client)
        
    def normalize_query(self, query: str) -> str:
        """Normalize query by adding spaces and cleaning"""
        query = re.sub(r'(ตำบล|แขวง|อำเภอ|เขต|จังหวัด|ต\.|อ\.|จ\.)', r'\1 ', query)
        query = re.sub(r'\s+', ' ', query)
        return query.strip()
    
    def detect_intent(self, query: str) -> QueryIntent:
        """Detect query intent from keywords"""
        query_lower = query.lower()
        
        # =====================================================================
        # CHECK FILTER INTENTS FIRST (must have a number to be valid)
        # e.g., "น้อยกว่า 50 แห่ง", "มากกว่า 100 โรง"
        # =====================================================================
        threshold = self.detect_threshold(query)
        if threshold is not None:
            # Check filter keywords
            filter_less_kw = INTENT_KEYWORDS.get(QueryIntent.FILTER_LESS_THAN, [])
            filter_greater_kw = INTENT_KEYWORDS.get(QueryIntent.FILTER_GREATER_THAN, [])
            filter_equals_kw = INTENT_KEYWORDS.get(QueryIntent.FILTER_EQUALS, [])
            
            if any(kw in query_lower for kw in filter_less_kw):
                return QueryIntent.FILTER_LESS_THAN
            elif any(kw in query_lower for kw in filter_greater_kw):
                return QueryIntent.FILTER_GREATER_THAN
            elif any(kw in query_lower for kw in filter_equals_kw):
                return QueryIntent.FILTER_EQUALS
        
        # Check "น้อยที่สุด" first (more specific) - only if no threshold number
        least_keywords = INTENT_KEYWORDS[QueryIntent.RANKING_LEAST]
        if any(kw in query_lower for kw in least_keywords):
            return QueryIntent.RANKING_LEAST
        
        # Check "มากที่สุด" second
        most_keywords = INTENT_KEYWORDS[QueryIntent.RANKING_MOST]
        if any(kw in query_lower for kw in most_keywords):
            return QueryIntent.RANKING_MOST
        
        # Check for school detail queries
        school_detail_kw = INTENT_KEYWORDS.get(QueryIntent.SCHOOL_DETAIL, [])
        if any(kw in query_lower for kw in school_detail_kw):
            return QueryIntent.SCHOOL_DETAIL
        
        # ✨ Check COMPARE FIRST (before count/list) - it's more specific
        compare_kw = INTENT_KEYWORDS.get(QueryIntent.COMPARE, [])
        if any(kw in query_lower for kw in compare_kw):
            # Additional check: must have multiple provinces or "กับ" pattern
            provinces_in_query = [p for p in THAI_PROVINCES if p.lower() in query_lower]
            if len(provinces_in_query) >= 2 or 'กับ' in query_lower or 'vs' in query_lower:
                return QueryIntent.COMPARE
        
        # Check for school count queries
        school_count_kw = INTENT_KEYWORDS.get(QueryIntent.SCHOOL_COUNT, [])
        if any(kw in query_lower for kw in school_count_kw):
            return QueryIntent.SCHOOL_COUNT
        
        # Check for school list queries
        school_list_kw = INTENT_KEYWORDS.get(QueryIntent.SCHOOL_LIST, [])
        if any(kw in query_lower for kw in school_list_kw):
            return QueryIntent.SCHOOL_LIST
        
        # Check for general school search
        school_search_kw = INTENT_KEYWORDS.get(QueryIntent.SCHOOL_SEARCH, [])
        if any(kw in query_lower for kw in school_search_kw):
            if any(p.lower() in query_lower for p in THAI_PROVINCES):
                return QueryIntent.SCHOOL_LIST
            return QueryIntent.SCHOOL_SEARCH
        
        # Check other intents
        for intent in [QueryIntent.COMPARE, QueryIntent.COUNT, QueryIntent.LIST]:
            keywords = INTENT_KEYWORDS.get(intent, [])
            if any(kw in query_lower for kw in keywords):
                return intent
        
        if any(kw in query_lower for kw in ['ตำบล', 'อำเภอ', 'จังหวัด', 'เขต', 'แขวง']):
            return QueryIntent.COUNT
        
        return QueryIntent.SEARCH
    
    def detect_threshold(self, query: str) -> Optional[int]:
        """Extract threshold number from query (e.g., 'น้อยกว่า 50 แห่ง' -> 50)"""
        import re
        # Match Thai or Arabic numerals followed by optional unit
        # Patterns: "น้อยกว่า 50 แห่ง", "มากกว่า ๑๐๐ โรง"
        patterns = [
            r'(?:น้อยกว่า|มากกว่า|ต่ำกว่า|สูงกว่า|เกิน|ไม่เกิน|ไม่ถึง|เท่ากับ)\s*(\d+)',
            r'(\d+)\s*(?:แห่ง|โรง|โรงเรียน|แห่งขึ้นไป|แห่งลงมา)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    continue
        return None
    
    def detect_region(self, query: str) -> Optional[str]:
        """Detect region from query"""
        query_lower = query.lower()
        
        each_region_keywords = [
            'แต่ละภาค', 'ทุกภาค', 'สรุปภาค', 'รายภาค',
            'ภาคไหน', 'ภาค ไหน', 'ภาคใด', 'ภาค ใด',
            'ภูมิภาคไหน', 'ภูมิภาคใด',
        ]
        if any(kw in query_lower for kw in each_region_keywords):
            return "each_region"
            
        for region_name in REGIONS.keys():
            if region_name in query_lower:
                return region_name
        return None
    
    def detect_province(self, query: str) -> Optional[str]:
        """Detect province from query"""
        query_lower = query.lower()
        
        for province in THAI_PROVINCES:
            if province.lower() in query_lower:
                return province
        
        for alias, full_name in PROVINCE_ALIASES.items():
            if alias.lower() in query_lower:
                return full_name
        
        return None
    
    def detect_bangkok(self, query: str) -> bool:
        """Auto-detect Bangkok from keywords"""
        query_lower = query.lower()
        has_khet = 'เขต' in query_lower and 'เขตพื้นที่' not in query_lower
        has_khwaeng = 'แขวง' in query_lower
        return has_khet or has_khwaeng
    
    def detect_popular_district(self, query: str) -> tuple:
        """Detect popular district names (e.g., หาดใหญ่, เบตง) and return (district, province)"""
        query_lower = query.lower()
        for district, province in POPULAR_DISTRICTS.items():
            if district.lower() in query_lower:
                return (district, province)
        return (None, None)
    
    def extract_entities(self, query: str) -> Dict[str, Optional[str]]:
        """Extract all entities from query"""
        normalized = self.normalize_query(query)
        query_lower = normalized.lower()
        
        entities = {
            'province': None,
            'district': None,
            'subdistrict': None,
            'agency': None,
            'region': None
        }
        
        entities['region'] = self.detect_region(query)
        entities['province'] = self.detect_province(query)
        
        # Bug fix: Detect popular bare district names (e.g., "หาดใหญ่" without "อำเภอ")
        popular_district, popular_province = self.detect_popular_district(query)
        if popular_district:
            entities['district'] = popular_district
            # If province wasn't detected, use the one associated with district
            if not entities['province']:
                entities['province'] = popular_province
        
        if not entities['province'] and self.detect_bangkok(query):
            entities['province'] = 'กรุงเทพมหานคร'

        
        cleaned = normalized
        noise_words = [
            'มี', 'กี่', 'โรง', 'โรงเรียน', 'แห่ง', 'เท่าไหร่', 'ทำไหร่', 
            'จำนวน', 'ทั้งหมด', 'บ้าง', 'ครับ', 'ค่ะ', 'คะ', 'เรียน',
            'ของ', 'ใน', 'ที่', 'ซึ่ง', 'มากที่สุด', 'น้อยที่สุด',
            'เยอะที่สุด', 'น้อยสุด', 'มากสุด', 'อันดับ',
            # Bug fix: exclude question words and abbreviations
            'อะไร', 'ไหน', 'อะไรบ้าง', 'มีอะไรบ้าง', 'รายชื่อ', 'รายการ',
            'ระหว่าง', 'กับ', 'และ', 'หรือ', 'เปรียบเทียบ', 'เทียบ',
            'รร', 'ร.ร.', 'รร.', 'ร.ร'  # School abbreviations
        ]
        for word in noise_words:
            cleaned = cleaned.replace(word, ' ')
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Extract district/subdistrict
        combined_match = re.search(
            r'(?:ตำบล|แขวง|ต\.)\s*([ก-๙]+)\s+(?:อำเภอ|เขต|อ\.)\s*([ก-๙]+)',
            cleaned
        )
        if combined_match:
            entities['subdistrict'] = combined_match.group(1).strip()
            entities['district'] = combined_match.group(2).strip()
        else:
            sub_match = re.search(r'(?:ตำบล|แขวง|ต\.)\s*([ก-๙]+)', cleaned)
            if sub_match:
                entities['subdistrict'] = sub_match.group(1).strip()
            
            dist_match = re.search(r'(?:อำเภอ|เขต|อ\.)\s*([ก-๙]+)', cleaned)
            if dist_match:
                entities['district'] = dist_match.group(1).strip()
        
        if entities['province']:
            cleaned = cleaned.replace(entities['province'], '').strip()
        
        structural_words = ['จังหวัด', 'อำเภอ', 'ตำบล', 'แขวง', 'เขต', 'จ.', 'อ.', 'ต.']
        for w in structural_words:
            cleaned = cleaned.replace(w, '')
        
        # Filter out agency aliases
        agency_alias_set = set(a.lower() for a in AGENCY_ALIASES.keys())
        agency_keywords = ['สังกัด', 'หน่วยงาน', 'ของ', 'ใน', 'ที่มี', 'ที่']
        national_keywords = [
            'ประเทศไทย', 'ประเทศ', 'ทั่วประเทศ', 'ทั้งประเทศ', 'ทั้งหมด', 'รวม', 'ไทย',
            'ทุกสังกัด', 'ทุกหน่วยงาน', 'ทุกอำเภอ', 'ทุกจังหวัด', 'ทุกตำบล', 'ทุกภาค',
            'สังกัดอื่น', 'สังกัดต่างๆ', 'หน่วยงานอื่น', 'หน่วยงานต่างๆ',
            'สรุป', 'รายละเอียด', 'ข้อมูล', 'ขอ', 'ดู', 'แสดง'
        ]
        exclusion_set = agency_alias_set.union(set(agency_keywords)).union(set(national_keywords))
        
        def should_exclude_word(word: str) -> bool:
            word_lower = word.lower()
            # Bug fix: add question words and compare words to exclusion
            exclude_keywords = [
                'สังกัด', 'หน่วยงาน', 'ทั้งหมด', 'ทั้งนั้น', 'ทุก', 'รวม', 'สรุป', 'ขอ', 'ดู', 'แสดง',
                'อะไร', 'ไหน', 'บ้าง', 'ระหว่าง', 'กับ', 'เปรียบเทียบ', 'เทียบ',
                'มากที่สุด', 'น้อยที่สุด', 'หนึ่ง', 'สอง', 'สาม'
            ]
            if any(kw in word_lower for kw in exclude_keywords):
                return True
            return word_lower in exclusion_set
        
        words = [w.strip() for w in cleaned.split() 
                 if len(w.strip()) >= 2 
                 and re.match(r'[ก-๙]+', w) 
                 and not should_exclude_word(w.strip())]
        
        # Skip words that are province short names, region names, or already extracted province
        province_short_names = [
            'กรุงเทพ', 'กรุงเทพฯ', 'กทม', 'กทม.', 'เชียงใหม่', 'ภูเก็ต', 'ขอนแก่น',
            'นครราชสีมา', 'สงขลา', 'อุดรธานี', 'ชลบุรี', 'เชียงราย',
            'โคราช', 'หาดใหญ่', 'เบตง', 'มหาสารคาม', 'อุบลราชธานี',  # Common aliases
            # Region names - don't treat as subdistrict
            'ภาคเหนือ', 'ภาคใต้', 'ภาคกลาง', 'ภาคอีสาน', 'ภาคตะวันออก', 'ภาคตะวันตก',
            'ภาคตะวันออกเฉียงเหนือ', 'ตะวันออกเฉียงเหนือ', 'อีสาน', 'เหนือ', 'ใต้', 'กลาง'
        ]
        words = [w for w in words if w not in province_short_names 
                 and w != (entities.get('province') or '').replace('มหานคร', '')
                 and w not in REGIONS.keys()]  # Also exclude region names
        
        if len(words) == 1 and not entities['subdistrict'] and not entities['district']:
            word = words[0]
            if word.startswith('เมือง'):
                entities['district'] = word
            else:
                entities['subdistrict'] = word
        elif len(words) >= 2 and not entities['subdistrict'] and not entities['district']:
            entities['subdistrict'] = words[0]
            entities['district'] = words[1]
        
        # Detect agency
        for alias, full_name in AGENCY_ALIASES.items():
            if alias.lower() in query_lower:
                entities['agency'] = full_name
                break
        
        logger.debug(f"Extracted entities: {entities}")
        return entities
    
    def detect_level(self, query: str, entities: Dict) -> QueryLevel:
        """Detect query level from entities and keywords"""
        query_lower = query.lower()
        
        agency_keywords = ['สังกัด', 'หน่วยงาน', 'สพฐ', 'สพฐ.', 'เอกชน', 'อปท', 'อปท.', 
                          'กรมส่งเสริม', 'เทศบาล', 'อบต', 'อบจ',
                          'สำนักงานคณะกรรมการ', 'กรม', 'สช', 'สช.']
        has_agency_kw = any(kw in query_lower for kw in agency_keywords)
        
        has_subdistrict_kw = any(kw in query_lower for kw in ['ตำบล', 'แขวง', 'ต.'])
        has_district_kw = any(kw in query_lower for kw in ['อำเภอ', 'เขต', 'อ.'])
        has_province = entities.get('province') is not None
        has_region = entities.get('region') is not None
        
        # Check region keywords
        region_keywords = ['ภาค', 'ภาคเหนือ', 'ภาคใต้', 'ภาคกลาง', 'ภาคอีสาน', 'ภาคตะวันออก', 'ภาคตะวันตก']
        has_region_kw = any(kw in query_lower for kw in region_keywords)
        
        if has_agency_kw:
            if has_province:
                return QueryLevel.PROVINCE
            return QueryLevel.AGENCY
        
        if has_subdistrict_kw or entities.get('subdistrict'):
            return QueryLevel.SUBDISTRICT
        if has_district_kw or entities.get('district'):
            return QueryLevel.DISTRICT
        
        # Check for region before province
        if has_region or has_region_kw:
            return QueryLevel.REGION
        
        if has_province:
            return QueryLevel.PROVINCE
        
        return QueryLevel.PROVINCE
    
    def parse(self, query: str) -> ParsedQuery:
        """Parse query into structured format"""
        entities = self.extract_entities(query)
        query_lower = query.lower()

        # =====================================================================
        # QUICK-PATH: Ranking detection (avoid LLM misrouting to school search)
        # e.g., "จังหวัดไหนมีนักเรียนมากที่สุด"
        # =====================================================================
        least_keywords = INTENT_KEYWORDS.get(QueryIntent.RANKING_LEAST, [])
        most_keywords = INTENT_KEYWORDS.get(QueryIntent.RANKING_MOST, [])
        has_least = any(kw in query_lower for kw in least_keywords)
        has_most = any(kw in query_lower for kw in most_keywords)
        if has_least or has_most:
            intent = QueryIntent.RANKING_LEAST if has_least else QueryIntent.RANKING_MOST
            return ParsedQuery(
                intent=intent,
                original_query=query,
                raw_query=query,
                level=self.detect_level(query, entities),
                province=entities.get('province'),
                district=entities.get('district'),
                subdistrict=entities.get('subdistrict'),
                school_name=None,
                agency=entities.get('agency'),
                region=entities.get('region'),
                min_students=entities.get('min_students'),
                max_students=entities.get('max_students'),
                min_teachers=entities.get('min_teachers'),
                max_teachers=entities.get('max_teachers'),
                area_name=entities.get('area_name'),
                person_type=entities.get('person_type'),
                coordinates_intent=entities.get('coordinates_intent', False),
                details_intent=entities.get('details_intent', False),
            )
        
        # SMART ROUTING: Use LLM for complex queries (more accurate), keywords for simple ones
        # LLM handles: COMPARE, RANKING, ambiguous multi-entity queries
        # Keywords handle: simple COUNT, LIST, DETAIL queries
        is_complex = len(query) > 15 or any(kw in query_lower for kw in ['เปรียบเทียบ', 'เทียบ', 'กับ', 'มากที่สุด', 'น้อยที่สุด', 'อันดับ'])
        
        llm_result = None
        if is_complex:
            llm_result = self.llm_classifier.classify(query)
        
        # Fallback to keyword-based detection if LLM fails or for simple queries
        keyword_intent = self.detect_intent(query) if not llm_result else None
        
        if llm_result:
            intent_mapping = {
                'SCHOOL_COUNT': QueryIntent.SCHOOL_COUNT,
                'STUDENT_COUNT': QueryIntent.STUDENT_COUNT,
                'TEACHER_COUNT': QueryIntent.TEACHER_COUNT,
                'RATIO': QueryIntent.RATIO,
                'SCHOOL_LIST': QueryIntent.SCHOOL_LIST,
                'SCHOOL_DETAIL': QueryIntent.SCHOOL_DETAIL,
                'SCHOOL_SEARCH': QueryIntent.SCHOOL_SEARCH,
                'COMPARE': QueryIntent.COMPARE,
                'RANKING_MOST': QueryIntent.RANKING_MOST,
                'RANKING_LEAST': QueryIntent.RANKING_LEAST,
                'LOAD_MORE': QueryIntent.LOAD_MORE,
                'FILTER_LESS_THAN': QueryIntent.FILTER_LESS_THAN,
                'FILTER_GREATER_THAN': QueryIntent.FILTER_GREATER_THAN,
                'FILTER_EQUALS': QueryIntent.FILTER_EQUALS,
                'GENERAL': QueryIntent.UNKNOWN,
            }
            
            llm_intent = llm_result.get('intent', 'GENERAL')
            intent = intent_mapping.get(llm_intent, QueryIntent.UNKNOWN)
            
            # --- HYBRID EXTRACTION: Combine LLM entities with Regex fallback ---
            llm_entities = {}
            if self.llm:
                # Use a specific prompt to extract detailed filters
                llm_entities = self._extract_entities_llm(query)
            
            # Merge: LLM entities override Regex entities for complex fields, 
            # but we keep Regex for basic location if LLM missed it
            for k, v in llm_entities.items():
                if v is not None and k not in entities: # Prioritize existing or new? Let's say LLM is smarter for areas
                     entities[k] = v
                elif v is not None and k in ['min_students', 'max_students', 'min_teachers', 'max_teachers', 'area_name', 'person_type']:
                     entities[k] = v # Always trust LLM for these new fields
            
            # Extract standard fields
            is_advanced_query = any(k in llm_entities for k in ['min_students', 'area_name', 'min_teachers', 'person_type'])
            
            if is_advanced_query:
                # 🛑 STRICT MODE: For advanced queries, trust LLM 100% to avoid regex noise (e.g. "มากกว่า" -> district)
                region = llm_result.get('region')
                province = llm_result.get('province')
                district = llm_result.get('district')
                subdistrict = llm_result.get('subdistrict')
                agency = llm_result.get('agency')
                school_name = llm_result.get('school_name')
            else:
                # 🤝 HYBRID MODE: Fallback to regex for simple queries
                region = llm_result.get('region') or entities.get('region')
                province = llm_result.get('province') or entities.get('province')
                district = llm_result.get('district') or entities.get('district')
                subdistrict = llm_result.get('subdistrict') or entities.get('subdistrict')
                agency = llm_result.get('agency') or entities.get('agency')
                school_name = llm_result.get('school_name') or entities.get('school_name') 
            
            return ParsedQuery(
                intent=intent,
                original_query=query,
                level=self.detect_level(query, entities),
                province=province,
                district=district,
                subdistrict=subdistrict,
                school_name=school_name,
                agency=agency,
                region=region,
                # Populate new fields
                min_students=entities.get('min_students'),
                max_students=entities.get('max_students'),
                min_teachers=entities.get('min_teachers'),
                max_teachers=entities.get('max_teachers'),
                area_name=entities.get('area_name'),
                coordinates_intent=entities.get('coordinates_intent', False),
                details_intent=entities.get('details_intent', False),
                person_type=entities.get('person_type')
            )

    def _extract_entities_llm(self, query: str) -> Dict[str, Any]:
        """Use LLM to extract advanced entities (students, teachers, area, etc.)"""
        try:
            prompt = f"""
            Extract entities from this Thai education query.
            Return ONLY a valid JSON object. No markdown.
            
            Query: "{query}"
            
            Fields to extract:
            - min_students (int): e.g. "มากว่า 100 คน" -> 100
            - max_students (int): e.g. "น้อยกว่า 500 คน" -> 500
            - min_teachers (int)
            - max_teachers (int)
            - area_name (str): e.g. "สพป.ปัตตานี เขต 1", "สพม.สงขลา" (Normalize strictly if possible)
            - person_type (str): e.g. "ลูกจ้างชั่วคราว", "พนักงานราชการ", "ครูอัตราจ้าง", "ครูธุรการ"
            - coordinates_intent (bool): true if asking for map/location/gps
            - details_intent (bool): true if asking for address/phone/details
            - province (str): Thai province name
            - district (str): Thai district name
            - subdistrict (str): Thai subdistrict name
            - school_name (str)
            - agency (str)
            
            JSON:
            """
            
            response = self.llm.generate_content(prompt, timeout=15)
            if not response or not response.text:
                return {}
                
            # Clean JSON
            cleaned = response.text.strip()
            if cleaned.startswith('```json'): prefix = 7
            elif cleaned.startswith('```'): prefix = 3
            else: prefix = 0
            
            if cleaned.endswith('```'): 
                cleaned = cleaned[prefix:-3]
            else:
                cleaned = cleaned[prefix:]
                
            import json
            data = json.loads(cleaned.strip())
            return data
            
        except Exception as e:
            logger.error(f"LLM Entity Extraction failed: {e}")
            return {}
            school_name = llm_result.get('school_name')
            
            # Fix: If subdistrict is actually a region name, clear it and set region instead
            region_names = ['ภาคเหนือ', 'ภาคใต้', 'ภาคกลาง', 'ภาคอีสาน', 'ภาคตะวันออก', 'ภาคตะวันตก',
                           'ภาคตะวันออกเฉียงเหนือ', 'อีสาน', 'เหนือ', 'ใต้', 'กลาง']
            if subdistrict and any(r in subdistrict for r in region_names):
                if not region:
                    region = subdistrict
                subdistrict = None
            
            # Normalize province using LocationLookup (fuzzy match against DB)
            if province and self.location_lookup:
                normalized_province = self.location_lookup.normalize_province(province)
                if normalized_province:
                    province = normalized_province
            
            # Normalize district using LocationLookup
            if district and self.location_lookup:
                normalized_district = self.location_lookup.normalize_district(district, province)
                if normalized_district:
                    district = normalized_district
            
            # Normalize subdistrict using LocationLookup
            if subdistrict and self.location_lookup:
                normalized_subdistrict = self.location_lookup.normalize_subdistrict(subdistrict, province, district)
                if normalized_subdistrict:
                    subdistrict = normalized_subdistrict
            
            # Get threshold from LLM response or detect from query
            threshold = llm_result.get('threshold') or self.detect_threshold(query)
            threshold_operator = None
            if intent == QueryIntent.FILTER_LESS_THAN:
                threshold_operator = "<"
            elif intent == QueryIntent.FILTER_GREATER_THAN:
                threshold_operator = ">"
            elif intent == QueryIntent.FILTER_EQUALS:
                threshold_operator = "="
            
            level = self.detect_level(query, entities)
            
            logger.info(f"🎯 Intent: {intent.value}, Level: {level.value}")
            logger.info(f"   Region: {region}, Province: {province}, District: {district}, Subdistrict: {subdistrict or 'None'}")
            if threshold:
                logger.info(f"   Threshold: {threshold_operator} {threshold}")
            
            return ParsedQuery(
                intent=intent,
                level=level,
                province=province,
                district=district,
                subdistrict=subdistrict,
                agency=agency,
                region=region,
                original_query=query,
                normalized_query=self.normalize_query(query),
                confidence=0.95,
                school_name=school_name,
                threshold=threshold,
                threshold_operator=threshold_operator
            )
        
        # Fallback to keyword matching (already computed above)
        logger.info("⚡ Using keyword-based intent (no LLM)")
        intent = keyword_intent  # Already computed at the start
        level = self.detect_level(query, entities)
        
        # Detect threshold for filter queries
        threshold = self.detect_threshold(query)
        threshold_operator = None
        if intent == QueryIntent.FILTER_LESS_THAN:
            threshold_operator = "<"
        elif intent == QueryIntent.FILTER_GREATER_THAN:
            threshold_operator = ">"
        elif intent == QueryIntent.FILTER_EQUALS:
            threshold_operator = "="
        
        logger.info(f"🎯 Intent: {intent.value}, Level: {level.value}")
        logger.info(f"   Region: {entities.get('region')}, Province: {entities.get('province')}, School: {entities.get('school_name', 'None')}")
        if threshold:
            logger.info(f"   Threshold: {threshold_operator} {threshold}")
        
        # Normalize location entities (same as LLM path)
        province = entities.get('province')
        district = entities.get('district')
        subdistrict = entities.get('subdistrict')
        
        if province and self.location_lookup:
            normalized_province = self.location_lookup.normalize_province(province)
            if normalized_province:
                province = normalized_province
        
        if district and self.location_lookup:
            normalized_district = self.location_lookup.normalize_district(district, province)
            if normalized_district:
                district = normalized_district
        
        if subdistrict and self.location_lookup:
            normalized_subdistrict = self.location_lookup.normalize_subdistrict(subdistrict, province, district)
            if normalized_subdistrict:
                subdistrict = normalized_subdistrict
        
        return ParsedQuery(
            intent=intent,
            level=level,
            province=province,
            district=district,
            subdistrict=subdistrict,
            agency=entities.get('agency'),
            region=entities.get('region'),
            original_query=query,
            normalized_query=self.normalize_query(query),
            confidence=0.8 if province or district else 0.5,
            threshold=threshold,
            threshold_operator=threshold_operator
        )
