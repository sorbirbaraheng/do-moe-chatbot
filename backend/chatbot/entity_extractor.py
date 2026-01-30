"""
LLM-based Entity Extraction Module

ใช้ LLM เพื่อแปลงคำที่ผู้ใช้พิมพ์ให้ตรงกับค่าในฐานข้อมูล
เช่น "ครูบรรจุ" → "ข้าราชการครู"
"""

import logging
import json
from typing import Optional, Dict, List, Any
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from .constants import COLLECTION_NAMES

logger = logging.getLogger(__name__)

# Cache for valid values (loaded once at startup)
_VALID_VALUES_CACHE: Dict[str, List[str]] = {}


def _get_qdrant_client() -> QdrantClient:
    """Get Qdrant client instance"""
    return QdrantClient(host='203.159.242.144', port=6333)


def fetch_valid_values() -> Dict[str, List[str]]:
    """
    ดึงค่าที่ถูกต้องทั้งหมดจาก Qdrant เพื่อใช้เป็น reference
    เรียกครั้งเดียวตอน startup แล้ว cache ไว้
    """
    global _VALID_VALUES_CACHE
    
    if _VALID_VALUES_CACHE:
        return _VALID_VALUES_CACHE
    
    logger.info("🔄 Fetching valid values from Qdrant for entity extraction...")
    
    try:
        client = _get_qdrant_client()
        
        # Fetch unique person_types
        results = client.scroll('edu_teachers_v5', limit=5000, with_payload=True)
        person_types = set()
        for r in results[0]:
            pt = r.payload.get('metadata', {}).get('person_type')
            if pt:
                person_types.add(pt)
        
        # Fetch unique grades
        results = client.scroll('edu_students_v5', limit=5000, with_payload=True)
        grades = set()
        for r in results[0]:
            g = r.payload.get('metadata', {}).get('grade')
            if g:
                grades.add(g)
        
        # Fetch unique agencies
        results = client.scroll(COLLECTION_NAMES["schools"], limit=5000, with_payload=True)
        agencies = set()
        area_names = set()  # NEW: Fetch unique area names (e.g. สพป. เชียงใหม่ เขต 1)
        districts = set()   # NEW: Fetch unique districts from DB
        
        for r in results[0]:
            meta = r.payload.get('metadata', r.payload)
            
            a = meta.get('agency')
            if a:
                agencies.add(a)
                
            area = meta.get('area_name')
            if area:
                area_names.add(area)
                
            d = meta.get('district')
            if d:
                districts.add(d)
        
        _VALID_VALUES_CACHE = {
            'person_type': sorted(list(person_types)),
            'grade': sorted(list(grades)),
            'agency': sorted(list(agencies)),
            'area_name': sorted(list(area_names)),  # NEW
            'district': sorted(list(districts)),    # NEW
        }
        
        logger.info(f"✅ Loaded valid values: {len(person_types)} person_types, {len(grades)} grades, {len(agencies)} agencies, {len(area_names)} areas, {len(districts)} districts")
        return _VALID_VALUES_CACHE
    
    except Exception as e:
        logger.error(f"❌ Failed to fetch valid values: {e}")
        return {'person_type': [], 'grade': [], 'agency': [], 'area_name': [], 'district': []}


def extract_entities_via_llm(question: str, llm_client: Any) -> Dict[str, Optional[str]]:
    """
    ใช้ LLM extract entities จากคำถามผู้ใช้
    โดยบังคับให้ LLM เลือกจากค่าที่ถูกต้องเท่านั้น
    
    Args:
        question: คำถามของผู้ใช้
        llm_client: LLM client instance (Groq/Gemini)
    
    Returns:
        Dict with extracted entities: person_type, grade, agency
    """
    valid_values = fetch_valid_values()
    
    # สร้าง prompt ที่บังคับ LLM เลือกจาก list
    prompt = f"""คุณเป็น Entity Extractor สำหรับระบบการศึกษาไทย

คำถามผู้ใช้: "{question}"

กรุณา extract ข้อมูลต่อไปนี้จากคำถาม (ถ้ามี):

1. **person_type** (ประเภทบุคลากร): เลือกจากค่าต่อไปนี้เท่านั้น หรือ null ถ้าไม่มี
   {valid_values.get('person_type', [])}

2. **grade** (ระดับชั้น): เลือกจากค่าต่อไปนี้เท่านั้น หรือ null ถ้าไม่มี
   ตัวอย่าง: ป.1-6, ม.1-6, อนุบาล, ปวช., ปวส.
   
3. **agency** (สังกัด): เลือกจากค่าต่อไปนี้เท่านั้น หรือ null ถ้าไม่มี
   {valid_values.get('agency', [])}

4. **area_name** (เขตพื้นที่): เลือกจากค่าต่อไปนี้เท่านั้น หรือ null ถ้าไม่มี
   {valid_values.get('area_name', [])}

5. **district** (อำเภอ): เลือกจากค่าต่อไปนี้เท่านั้น หรือ null ถ้าไม่มี
   {valid_values.get('district', [])}

6. **intent** (เจตนา): เลือกจากค่าต่อไปนี้เท่านั้น หรือ null ถ้าไม่แน่ใจ
   - "count_students": ถามจำนวนนักเรียน
   - "count_teachers": ถามจำนวนครู/บุคลากร
   - "list_schools": ขอรายชื่อโรงเรียน
   - "search_schools": ค้นหาโรงเรียน (ทั่วไป)
   - "get_school_full_details": ขอที่อยู่/เบอร์โทร/พิกัด/ข้อมูลติดต่อ
   - "ranking": จัดอันดับ (มากสุด/น้อยสุด)
   - "compare": เปรียบเทียบ
   - "get_ratio": ถามอัตราส่วนครูต่อนักเรียน

**ตัวอย่างการแปลง:**
- "ครูบรรจุ" หรือ "ครูราชการ" → person_type: "ข้าราชการครู"
- "สพป เชียงใหม เขต 1" → area_name: "สพป. เชียงใหม่ เขต 1"
- "อำเภอเมือง" → district: "เมืองเชียงใหม่" (ถ้าบริบทชัดเจน) หรือ null
- "มีนักเรียนกี่คน" → intent: "count_students"
- "ขอเบอร์โทรโรงเรียน..." → intent: "get_school_full_details"

**ตอบเป็น JSON เท่านั้น:**
{{"intent": "...", "person_type": "...", "grade": "...", "agency": "...", "area_name": "...", "district": "..."}}
"""
    
    try:
        # Call LLM
        response = llm_client.generate_content(prompt)
        response_text = response.text.strip()
        
        # Extract JSON from response
        # Handle cases where LLM wraps in ```json ... ```
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0].strip()
        elif '```' in response_text:
            response_text = response_text.split('```')[1].split('```')[0].strip()
        
        result = json.loads(response_text)
        
        # Validate: ต้องอยู่ใน valid list เท่านั้น
        validated = {}
        
        # ... (validation logic for person_type, grade, agency as before) ...
        # Simplified for brevity in replacement, but ensuring all logic is present
        
        if result.get('person_type') and result['person_type'] in valid_values.get('person_type', []):
            validated['person_type'] = result['person_type']
        else:
            validated['person_type'] = None

        if result.get('grade'):
            for valid_grade in valid_values.get('grade', []):
                if result['grade'] in valid_grade or valid_grade in result['grade']:
                    validated['grade'] = valid_grade
                    break
            else:
                validated['grade'] = None
        else:
            validated['grade'] = None
            
        if result.get('agency') and result['agency'] in valid_values.get('agency', []):
            validated['agency'] = result['agency']
        else:
            validated['agency'] = None

        # NEW: Validate area_name
        if result.get('area_name') and result['area_name'] in valid_values.get('area_name', []):
            validated['area_name'] = result['area_name']
            logger.info(f"🎯 LLM extracted area_name: '{result['area_name']}'")
        else:
            validated['area_name'] = None

        # NEW: Validate district
        if result.get('district') and result['district'] in valid_values.get('district', []):
            validated['district'] = result['district']
            logger.info(f"🎯 LLM extracted district: '{result['district']}'")
        else:
            validated['district'] = None
        
        if result.get('intent') and result['intent'] in ["count_students", "count_teachers", "list_schools", "search_schools", "get_school_full_details", "ranking", "compare", "get_ratio"]:
            validated['intent'] = result['intent']
        else:
            validated['intent'] = None

        return validated
        
    except json.JSONDecodeError as e:
        logger.warning(f"⚠️ LLM response not valid JSON: {e}")
        return {'person_type': None, 'grade': None, 'agency': None}
    except Exception as e:
        logger.error(f"❌ LLM entity extraction failed: {e}")
        return {'person_type': None, 'grade': None, 'agency': None}


def extract_person_type_smart(question: str, llm_client: Any = None) -> Optional[str]:
    """
    Smart person_type extraction: ลอง keyword ก่อน ถ้าไม่เจอใช้ LLM
    
    Args:
        question: คำถามผู้ใช้
        llm_client: LLM client (optional, ถ้าไม่มีจะใช้ keyword only)
    
    Returns:
        person_type ที่ตรงกับ database หรือ None
    """
    valid_values = fetch_valid_values()
    person_types = valid_values.get('person_type', [])
    
    # 1. Try direct match first (เร็ว, ไม่เปลือง token)
    for pt in person_types:
        if pt in question:
            logger.info(f"👔 Direct match person_type: '{pt}'")
            return pt
    
    # 2. ถ้าไม่เจอ และมี LLM client → ใช้ LLM
    if llm_client:
        entities = extract_entities_via_llm(question, llm_client)
        return entities.get('person_type')
    
    return None


def extract_grade_smart(question: str, llm_client: Any = None) -> Optional[str]:
    """
    Smart grade extraction: ลอง keyword ก่อน ถ้าไม่เจอใช้ LLM
    """
    valid_values = fetch_valid_values()
    grades = valid_values.get('grade', [])
    
    # Common grade aliases
    grade_aliases = {
        'ป.1': 'ประถมศึกษาปีที่ 1/เกรด 1',
        'ป.2': 'ประถมศึกษาปีที่ 2/เกรด 2',
        'ป.3': 'ประถมศึกษาปีที่ 3/เกรด 3',
        'ป.4': 'ประถมศึกษาปีที่ 4/เกรด 4',
        'ป.5': 'ประถมศึกษาปีที่ 5/เกรด 5',
        'ป.6': 'ประถมศึกษาปีที่ 6/เกรด 6',
        'ม.1': 'มัธยมศึกษาปีที่ 1 /เกรด 7/ นาฎศิลป์ชั้นที่ 1',
        'ม.2': 'มัธยมศึกษาปีที่ 2 /เกรด 8/ นาฎศิลป์ชั้นที่ 2',
        'ม.3': 'มัธยมศึกษาปีที่ 3 /เกรด 9/ นาฎศิลป์ชั้นที่ 3',
        'ม.4': 'มัธยมศึกษาปีที่ 4/เกรด10',
        'ม.5': 'มัธยมศึกษาปีที่ 5/เกรด11',
        'ม.6': 'มัธยมศึกษาปีที่ 6/เกรด12',
    }
    
    # 1. Check aliases
    for alias, full_grade in grade_aliases.items():
        if alias in question:
            logger.info(f"📚 Alias match grade: '{alias}' → '{full_grade}'")
            return full_grade
    
    # 2. Direct match
    for g in grades:
        if g in question:
            logger.info(f"📚 Direct match grade: '{g}'")
            return g
    
    # 3. ถ้าไม่เจอ และมี LLM client → ใช้ LLM
    if llm_client:
        entities = extract_entities_via_llm(question, llm_client)
        return entities.get('grade')
    
    return None


def extract_area_smart(question: str, llm_client: Any = None) -> Optional[str]:
    """
    Smart area_name extraction: LLM-based only (since names are complex "สพป...")
    """
    if llm_client:
        entities = extract_entities_via_llm(question, llm_client)
        return entities.get('area_name')
    return None


def extract_district_smart(question: str, llm_client: Any = None) -> Optional[str]:
    """
    Smart district extraction: Try direct match -> LLM
    """
    valid_values = fetch_valid_values()
    districts = valid_values.get('district', [])
    
    # 1. Direct match (for simple names like "เมืองเชียงใหม่")
    for d in districts:
        if d in question and len(d) > 3: # Avoid short matches
             logger.info(f"🏙️ Direct match district: '{d}'")
             return d
             
    # 2. LLM fallback
    if llm_client:
        entities = extract_entities_via_llm(question, llm_client)
        return entities.get('district')
    
    return None
