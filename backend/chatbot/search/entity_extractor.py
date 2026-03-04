"""
LLM-based Entity Extraction Module

ใช้ LLM เพื่อแปลงคำที่ผู้ใช้พิมพ์ให้ตรงกับค่าในฐานข้อมูล
เช่น "ครูบรรจุ" → "ข้าราชการครู"
"""

import os
import re
import json
import time
import logging
from typing import Optional, Dict, List, Any
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from ..core.constants import COLLECTION_NAMES, THAI_PROVINCES, PROVINCE_ALIASES, REGIONS, AGENCY_ALIASES, YEAR_ALIASES

logger = logging.getLogger(__name__)

# Cache for valid values (loaded once at startup)
_VALID_VALUES_CACHE: Dict[str, List[str]] = {}
_VALID_VALUES_LAST_FAIL: float = 0.0
_VALID_VALUES_LAST_SUCCESS: float = 0.0

# Controls for valid-value prefetch (can disable for stability)
ENABLE_VALID_VALUES_FETCH = os.getenv("ENABLE_VALID_VALUES_FETCH", "1") != "0"
VALID_VALUES_RETRY_SECONDS = int(os.getenv("VALID_VALUES_RETRY_SECONDS", "300"))
_PROVINCE_LOWER_MAP: Dict[str, str] = {p.lower(): p for p in THAI_PROVINCES}
_REGION_LOWER_MAP: Dict[str, str] = {r.lower(): r for r in REGIONS.keys()}
_AGENCY_CANONICAL_MAP: Dict[str, str] = {
    # สพฐ
    "สพฐ": "สพฐ",
    "สพฐ.": "สพฐ",
    "พื้นฐาน": "สพฐ",
    "การศึกษาขั้นพื้นฐาน": "สพฐ",
    "สำนักงานคณะกรรมการการศึกษาขั้นพื้นฐาน": "สพฐ",
    # สช / เอกชน
    "สช": "สช",
    "สช.": "สช",
    "เอกชน": "สช",
    "ส่งเสริมการศึกษาเอกชน": "สช",
    "สำนักงานคณะกรรมการส่งเสริมการศึกษาเอกชน": "สช",
    # อปท / ท้องถิ่น
    "อปท": "อปท",
    "อปท.": "อปท",
    "ท้องถิ่น": "อปท",
    "กรมส่งเสริมการปกครองท้องถิ่น": "อปท",
    # กทม
    "กทม": "กทม",
    "กทม.": "กทม",
    "กรุงเทพมหานคร": "กทม",
    "สำนักการศึกษา กรุงเทพมหานคร": "กทม",
    "สำนักการศึกษา": "กทม",
    # สอศ / อาชีวะ
    "สอศ": "สอศ",
    "สอศ.": "สอศ",
    "อาชีวะ": "สอศ",
    "อาชีวศึกษา": "สอศ",
    "สำนักงานคณะกรรมการการอาชีวศึกษา": "สอศ",
    # ตชด
    "ตชด": "ตชด",
    "ตชด.": "ตชด",
    "ตำรวจตระเวนชายแดน": "ตชด",
    "กองบัญชาการตำรวจตระเวนชายแดน": "ตชด",
    # กศน
    "กศน": "กศน",
    "กศน.": "กศน",
    "กรมส่งเสริมการเรียนรู้": "กศน",
}
_AGENCY_CANONICAL_KEYS = list(_AGENCY_CANONICAL_MAP.keys())
_AGENCY_FULLNAME_TO_CANON = {v: k for k, v in AGENCY_ALIASES.items()} if AGENCY_ALIASES else {}


def _area_key(name: str) -> str:
    if not name:
        return ""
    return (
        name.lower()
        .replace("สพป.", "สพป")
        .replace("สพม.", "สพม")
        .replace("สพป", "สพป")
        .replace("สพม", "สพม")
        .replace("เขต ", "เขต")
        .replace(" ", "")
        .replace(".", "")
    )


def _best_fuzzy_match(value: str, candidates: List[str], min_ratio: float) -> Optional[str]:
    if not value or not candidates:
        return None
    v = value.strip()
    if not v:
        return None
    # Avoid fuzzy on very short strings to reduce false matches
    if len(v) < 3:
        return None
    try:
        import difflib
        best = None
        best_ratio = 0.0
        for c in candidates:
            ratio = difflib.SequenceMatcher(a=v, b=c).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best = c
        return best if best_ratio >= min_ratio else None
    except Exception:
        return None


def _normalize_province(value: Optional[str]) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    v = value.strip()
    if not v:
        return None
    # Strip common prefix
    if v.startswith("จังหวัด"):
        v = v.replace("จังหวัด", "").strip()
    if v.startswith("จ."):
        v = v.replace("จ.", "").strip()
    if v.startswith("จ "):
        v = v.replace("จ ", "").strip()
    # Alias map (กทม -> กรุงเทพมหานคร)
    if v in PROVINCE_ALIASES:
        v = PROVINCE_ALIASES[v]
    if v in THAI_PROVINCES:
        return v
    v_lower = v.lower()
    if v_lower in _PROVINCE_LOWER_MAP:
        return _PROVINCE_LOWER_MAP[v_lower]
    # Fuzzy match for misspellings
    min_ratio = 0.94 if len(v) <= 4 else 0.88
    return _best_fuzzy_match(v, THAI_PROVINCES, min_ratio)


def _normalize_region(value: Optional[str]) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    v = value.strip()
    if not v:
        return None
    region_aliases = {
        "อีสาน": "ภาคตะวันออกเฉียงเหนือ",
        "ภาคอีสาน": "ภาคตะวันออกเฉียงเหนือ",
        "ตะวันออกเฉียงเหนือ": "ภาคตะวันออกเฉียงเหนือ",
        "ภาคตะวันออกเฉียงเหนือ": "ภาคตะวันออกเฉียงเหนือ",
        "เหนือ": "ภาคเหนือ",
        "ใต้": "ภาคใต้",
        "กลาง": "ภาคกลาง",
        "ตะวันออก": "ภาคตะวันออก",
        "ตะวันตก": "ภาคตะวันตก",
    }
    if v in region_aliases:
        v = region_aliases[v]
    if v in REGIONS:
        return v
    v_lower = v.lower()
    if v_lower in _REGION_LOWER_MAP:
        return _REGION_LOWER_MAP[v_lower]
    # Fuzzy match for region (safer, small set)
    return _best_fuzzy_match(v, list(REGIONS.keys()), 0.84)


def _normalize_agency(value: Optional[str], valid_agencies: Optional[List[str]] = None) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    v = value.strip()
    if not v:
        return None

    # Direct canonical keyword map
    if v in _AGENCY_CANONICAL_MAP:
        return _AGENCY_CANONICAL_MAP[v]

    # If value is already a full official name, map to canonical if possible
    if v in _AGENCY_FULLNAME_TO_CANON:
        return _AGENCY_FULLNAME_TO_CANON[v]

    # Fuzzy match on known canonical keywords (avoid very short)
    if len(v) >= 4:
        min_ratio = 0.90 if len(v) <= 6 else 0.86
        fuzzy_key = _best_fuzzy_match(v, _AGENCY_CANONICAL_KEYS, min_ratio)
        if fuzzy_key:
            return _AGENCY_CANONICAL_MAP.get(fuzzy_key)

    # Fallback: match against known valid agencies from DB
    if valid_agencies:
        matched = _match_valid_value(v, valid_agencies)
        if matched:
            # If matched is a full official name, return canonical if we can
            if matched in _AGENCY_FULLNAME_TO_CANON:
                return _AGENCY_FULLNAME_TO_CANON[matched]
            return matched

    return None


def _normalize_area_name(value: Optional[str], valid_area_names: Optional[List[str]] = None) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    v = value.strip()
    if not v:
        return None

    # Normalize common variants: "สพป เชียงใหม่ เขต 1" -> "สพป. เชียงใหม่ เขต 1"
    v = v.replace("สพป", "สพป.").replace("สพม", "สพม.")
    v = v.replace("สพป..", "สพป.").replace("สพม..", "สพม.")
    v = v.replace("สพป.", "สพป. ").replace("สพม.", "สพม. ")
    v = " ".join(v.split()).strip()

    if not valid_area_names:
        return v

    key = _area_key(v)
    for cand in valid_area_names:
        if _area_key(cand) == key:
            return cand

    # Containment match
    matched = _match_valid_value(v, valid_area_names)
    if matched:
        return matched

    # Fuzzy match on normalized keys
    candidates = [(cand, _area_key(cand)) for cand in valid_area_names]
    best = None
    best_ratio = 0.0
    try:
        import difflib
        for cand, cand_key in candidates:
            ratio = difflib.SequenceMatcher(a=key, b=cand_key).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best = cand
    except Exception:
        return None

    return best if best_ratio >= 0.90 else None


def _normalize_district(value: Optional[str], valid_districts: Optional[List[str]] = None, province: Optional[str] = None) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    v = value.strip()
    if not v:
        return None

    # Strip common prefixes
    prefixes = ["อำเภอ", "อ.", "เขต", "แขวง", "ตำบล", "ต."]
    for prefix in prefixes:
        if v.startswith(prefix):
            v = v[len(prefix):].strip()
            break

    # Normalize "เมือง" with province context (if provided)
    if province and v == "เมือง":
        candidate = f"เมือง{province}"
        if valid_districts and candidate in valid_districts:
            return candidate

    if not valid_districts:
        return v

    if v in valid_districts:
        return v

    # Try "เมือง{province}" if district startswith เมือง and province provided
    if province and v.startswith("เมือง"):
        candidate = f"เมือง{province}"
        if candidate in valid_districts:
            return candidate

    matched = _match_valid_value(v, valid_districts)
    if matched:
        return matched

    # Fuzzy for misspellings (high threshold)
    min_ratio = 0.92 if len(v) <= 4 else 0.88
    return _best_fuzzy_match(v, valid_districts, min_ratio)


def _normalize_grade(value: Optional[str], valid_grades: Optional[List[str]] = None) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    v = value.strip()
    if not v:
        return None

    # Normalize common variants (Thai/Arabic)
    v = v.replace("ชั้น", "").replace("ระดับ", "").strip()
    v = v.replace("ประถม", "ป.").replace("มัธยม", "ม.")
    v = v.replace("ป ", "ป.").replace("ม ", "ม.")
    v = v.replace("ป.", "ป.").replace("ม.", "ม.")
    v = v.replace("ปป", "ป.").replace("มม", "ม.")
    v = v.replace("อนุบาล", "อ.").replace("อ ", "อ.")
    v = " ".join(v.split())

    # Handle ranges like "ป.1-6", "ม.1 ถึง ม.3"
    if any(sep in v for sep in ["-", "ถึง", "–", "to"]):
        # Keep raw range if DB doesn't store ranges; ask-back will handle if needed
        return v

    # Standardize e.g. "ป.1", "ม.2", "อ.1"
    # If value is just a number with context words, try infer
    for prefix in ["ป.", "ม.", "อ.", "ปวช.", "ปวส."]:
        if v.startswith(prefix):
            return v

    # Try match against valid grades list
    if valid_grades:
        matched = _match_valid_value(v, valid_grades)
        if matched:
            return matched
        # Fuzzy
        min_ratio = 0.90 if len(v) <= 4 else 0.86
        return _best_fuzzy_match(v, valid_grades, min_ratio)

    return v


def _normalize_gender(value: Optional[str]) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    v = value.strip().lower()
    if v in ["ชาย", "male", "ผู้ชาย", "เพศชาย"]:
        return "ชาย"
    if v in ["หญิง", "female", "ผู้หญิง", "เพศหญิง"]:
        return "หญิง"
    return None


def _coerce_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        digits = "".join(ch for ch in value if ch.isdigit())
        if digits:
            try:
                return int(digits)
            except ValueError:
                return None
    return None


def _match_valid_value(value: Optional[str], valid_list: List[str]) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    v = value.strip()
    if v in valid_list:
        return v
    # Fuzzy containment (safe enough for domain-specific labels)
    for valid in valid_list:
        if v in valid or valid in v:
            return valid
    return None


def extract_query_structured_via_llm(question: str, llm_client: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Structured query extraction using LLM (tool + params + clarification flags).
    Enforces minimal validation for province/region and normalizes key params.
    """
    if not llm_client:
        return {
            "tool": None,
            "params": {},
            "needs_clarification": True,
            "clarification_question": "ขอรายละเอียดเพิ่มอีกนิดได้ไหมครับ เช่น จังหวัด/โรงเรียน/ประเภทข้อมูลที่ต้องการ"
        }

    # Build lightweight context string (avoid token-heavy dumps)
    context_str = "None"
    if context:
        c_items = []
        if context.get("last_school_name") or context.get("current_school"):
            c_items.append(f"school={context.get('last_school_name') or context.get('current_school')}")
        if context.get("last_province") or context.get("current_province"):
            c_items.append(f"province={context.get('last_province') or context.get('current_province')}")
        if context.get("last_region") or context.get("current_region"):
            c_items.append(f"region={context.get('last_region') or context.get('current_region')}")
        if context.get("last_district") or context.get("current_district"):
            c_items.append(f"district={context.get('last_district') or context.get('current_district')}")
        if context.get("last_agency") or context.get("current_agency"):
            c_items.append(f"agency={context.get('last_agency') or context.get('current_agency')}")
        if context.get("last_scope_type") and context.get("last_scope_value"):
            c_items.append(f"scope={context.get('last_scope_type')}:{context.get('last_scope_value')}")
        last_ai = context.get("last_ai_response")
        if last_ai:
            clean_last_ai = last_ai.replace("\n", " ").strip()
            clean_last_ai = (clean_last_ai[:200] + "...") if len(clean_last_ai) > 200 else clean_last_ai
            c_items.append(f"last_ai=\"{clean_last_ai}\"")
        if c_items:
            context_str = "; ".join(c_items)

    reflection_instruction = ""
    if context and context.get("reflection_prompt"):
        reflection_instruction = f"\n\n🚨 [REFLECTION INSTRUCTION]: {context.get('reflection_prompt')}\n🚨 พิจารณาคำค้นหาเดิม และปรับลดเงื่อนไข หรือใช้เครื่องมืออื่นที่ตอบกว้างขึ้น เพื่อให้ได้ผลลัพธ์มาแสดงผล!"

    prompt = f"""
คุณเป็นระบบ Structured Extraction สำหรับแชทบอทข้อมูลการศึกษาไทย{reflection_instruction}

Context: {context_str}
User: "{question}"

⚡ PRONOUN RESOLUTION (สำคัญมาก!):
- ถ้าผู้ใช้พูดว่า "จังหวัดนี้", "ในจังหวัดนี้", "ของจังหวัดนี้" → ให้ดึง province จาก Context ด้านบน แล้วใส่ใน params
- ถ้าผู้ใช้พูดว่า "โรงเรียนนี้", "ของโรงเรียนนี้" → ให้ดึง school จาก Context ด้านบน แล้วใส่ใน params
- ตัวอย่าง: Context มี province=อุบลราชธานี, User ถามว่า "สังกัดไหนมีโรงเรียนมากที่สุดในจังหวัดนี้"
  → ใช้ ranking_by_agency(province="อุบลราชธานี", metric="schools")
- ⚠️ ห้ามปล่อยให้ "จังหวัดนี้" เป็น null เมื่อ Context มี province อยู่

เลือกเครื่องมือ (tool) และพารามิเตอร์ให้เหมาะสมที่สุด โดยตอบเป็น JSON เท่านั้น

Routing hints (อ้างอิงโครงสร้าง Qdrant v5):
- ข้อมูลโรงเรียน (ที่อยู่/พิกัด/ครู/นักเรียน/สังกัด) -> get_school_full_details หรือ search_schools (ใช้ edu_schools_v5)
- จำนวนครู/บุคลากร (แยกเพศ/ประเภท) -> count_teachers / analyze_teacher_distribution (edu_teachers_v5)
- จำนวนนักเรียน (แยกชั้น/เพศ) -> count_students / get_grade_distribution (edu_students_v5, edu_grade_summary_v5)
- อัตราส่วนครูต่อนักเรียน -> get_ratio / find_best_ratio_schools (edu_ratios_v5)
- ระบบการศึกษา (ในระบบ/นอกระบบ) -> count_by_system_type (edu_systems_v5)
- สัดส่วนเพศภาพรวมในพื้นที่ -> analyze_gender_ratio (edu_gender_overview_v5)
- เขตพื้นที่การศึกษา -> search_education_areas / get_education_area_info (edu_areas_v5)

⚡ RANKING — กฎสำคัญ (ถ้าถามเรื่อง มากที่สุด/น้อยที่สุด/สูงสุด/ต่ำสุด/อันดับ → ใช้ ranking):
  - metric: "schools"|"students"|"teachers"|"ratio"
  - order: "most" (มากที่สุด/สูงที่สุด/สูงสุด/เยอะที่สุด) | "least" (น้อยที่สุด/ต่ำที่สุด/ต่ำสุด)
  - scope: "province" (จังหวัดไหน) | "district" (อำเภอไหน/เขตไหน) | "subdistrict" (ตำบลไหน/แขวงไหน) | "school" (โรงเรียนไหน)
  - ⚠️ "อัตราส่วนครูต่อนักเรียน" → metric="ratio" (ไม่ใช่ "teachers" แม้มีคำว่า "ครู")
  - ⚠️ "ครูต่อเด็ก"/"ครูต่อนักเรียน" → metric="ratio"
  - ⚠️ ถ้าถามแบบ "จว.ไหนครูน้อยเมื่อเทียบกับเด็ก" → ใช้ ranking(metric=ratio, order=least, scope=province)
  - ⚠️ ถ้าถามแบบ "ที่ไหนนักเรียนต่อครูสูง" → ใช้ ranking(metric=ratio, order=most, scope=province)
  - ถ้ามี province ให้ใส่ province ด้วย (ranking ภายในจังหวัด)
  - ⚠️ **DRILL-DOWN — ถ้าถามจังหวัดไหน/อำเภอไหน/ตำบลไหน "ใน" ภาค/จังหวัด:**
    - "จังหวัดไหนในภาคกลางมีนักเรียนมากที่สุด" → ranking(metric=students, order=most, scope=province, region=ภาคกลาง)
    - "จังหวัดไหนในภาคใต้มีครูน้อยที่สุด" → ranking(metric=teachers, order=least, scope=province, region=ภาคใต้)
    - "อำเภอไหนในภาคใต้มีโรงเรียนเยอะที่สุด" → ranking(metric=schools, order=most, scope=district, region=ภาคใต้)
    - "อำเภอไหนในเชียงใหม่มีโรงเรียนมากที่สุด" → ranking(metric=schools, order=most, scope=district, province=เชียงใหม่)
    - "ตำบลไหนในเชียงใหม่มีนักเรียนเยอะสุด" → ranking(metric=students, order=most, scope=subdistrict, province=เชียงใหม่)
    - "จังหวัดไหนมีครูมากที่สุด" → ranking(metric=teachers, order=most, scope=province) (ทั้งประเทศ)
    - ⚠️ ถ้ามีคำว่า "ภาค" (ภาคเหนือ/ภาคใต้/ภาคกลาง...) → ใส่ region=ชื่อภาค
    - ⚠️ ถ้ามีคำว่า "จังหวัด" + "ใน" + "ภาค" → scope=province, region=ภาค
    - ⚠️ ถ้ามีคำว่า "อำเภอ" + "ใน" + "ภาค" → scope=district, region=ภาค

⚡ SCHOOL NAME — กฎสำคัญ:
  - ⚠️ ถ้ามีคำว่า "โรงเรียน[ชื่อ]" เช่น "โรงเรียนเมืองปัตตานี", "โรงเรียนสวนกุหลาบ" → ใช้ get_school_full_details(school_name="เมืองปัตตานี")
  - ⚠️ "โรงเรียน" + ชื่อเฉพาะ ≠ "จังหวัด" → ต้องใช้ school_name ไม่ใช่ province
  - ⚠️ "โรงเรียนเมืองX" คือชื่อโรงเรียน ไม่ใช่ province X
  - ตัวอย่าง: "โรงเรียนเมืองปัตตานีมีครูกี่คน" → get_school_full_details(school_name="เมืองปัตตานี") ไม่ใช่ get_province_summary(province="ปัตตานี")

⚡ MULTI-METRIC (ถ้าถามหลาย metric พร้อมกัน: ครู+นักเรียน+โรงเรียน):
  - ⚠️ ถ้ามีชื่อโรงเรียน → ใช้ get_school_full_details (ไม่ใช่ province_summary)
  - ถ้ามีจังหวัดแต่ไม่มีชื่อโรงเรียน → ใช้ get_province_summary
  - ถ้าถามเฉพาะ "ครู" → count_teachers, "นักเรียน" → count_students, "โรงเรียน" → count_schools

⚡ FILTER (ถ้ามีตัวเลขเงื่อนไข เช่น "มากกว่า 500 คน", "น้อยกว่า 100"):
  - ใช้ filter_schools(metric, operator, value, province, ...)
  - operator: "gt"|"gte"|"lt"|"lte"|"eq"

Allowed tools (พร้อมพารามิเตอร์):
- count_students (school_name, province, region, district, grade, gender, year)
- count_teachers (school_name, province, region, district, gender, person_type, year)
- count_schools (province, region, district, subdistrict, agency, year)
- list_schools (province, region, district, agency, limit, year)
- search_schools (school_name, province, region, district, agency, limit, year)
- get_school_full_details (school_name, province, year)
- get_ratio (school_name, province, year)
- ranking (metric, order, scope, province, region, limit, year, person_type)
- compare (entity1, entity2, metric, year)
- search_education_areas (area_name, province, district)
- get_province_summary (province, year)
- count_by_system_type (province, district, system_type, year)
- analyze_gender_ratio (province, district, year)
- get_grade_distribution (province, district, school_name, grade, year)
- find_best_ratio_schools (province, order, limit, year)
- analyze_teacher_distribution (province, district, region, person_type, year)
- ranking_by_agency (province, metric, limit, year)
- ranking_subdistricts (province, district, metric, order, limit, year)
- get_district_summary (province, district, year)
- compare_provinces (provinces, metrics, year)
- find_nearby_schools (latitude, longitude, radius_km, limit)
- advanced_school_search (province, district, agency, min_students, max_students, min_teachers, max_teachers, limit)
- filter_schools (metric, operator, value, province, region, district, subdistrict, limit, year)
- general_chat (ไม่มี params)

หมายเหตุสำคัญ:
- province ต้องเป็นชื่อจังหวัดมาตรฐานไทย (เช่น กรุงเทพมหานคร, เชียงใหม่)
- region ต้องเป็นชื่อภาค (เช่น ภาคเหนือ, ภาคใต้, ภาคตะวันออกเฉียงเหนือ)
- year เป็น **ตัวเลือก** — ถ้าผู้ใช้ระบุปี (เช่น "ปี 67", "ปี 2567", "พ.ศ. 2567") ให้ใส่ year=2567
- ⚠️ "ปี 67" = "ปี 2567" (บวก 2500)
- ⚠️ ถ้าผู้ใช้ไม่ระบุปี ไม่ต้องใส่ year (ระบบจะใช้ข้อมูลหลักอัตโนมัติ)
- ตั้ง data_required=true ถ้าเป็นคำถามเชิงข้อมูลจริง (จำนวน, รายชื่อ, อัตราส่วน, รายละเอียดโรงเรียน, สถิติ)
- ตั้ง data_required=false ถ้าเป็นคำถามทั่วไป/คำแนะนำ/นิยามที่ไม่ต้องใช้ฐานข้อมูล
- ขอรายละเอียดเพิ่มเฉพาะกรณีที่ "ขอบเขตหลัก" ไม่ชัด (เช่น ไม่รู้โรงเรียน/จังหวัด/ภาคเลย)

⚡ GRADE — การแปลงระดับชั้น (สำคัญมาก!):
- "ม 1"/"ม.1"/"มัธยม 1"/"มัธยมศึกษาปีที่ 1" → grade="ม.1"
- "ป 3"/"ป.3"/"ประถม 3"/"ประถมศึกษาปีที่ 3" → grade="ป.3"
- "อนุบาล 1"/"อนุบาล1" → grade="อนุบาล 1"
- "ปวช 1"/"ปวช.1" → grade="ปวช.1"
- ⚠️ ถ้าถาม "ชั้น ม.1 โรงเรียน X มีนักเรียนกี่คน" → count_students(school_name="X", grade="ม.1")
- ⚠️ ถ้าถาม "ชั้นไหนมีนักเรียนน้อยสุด ที่โรงเรียน X" → get_grade_distribution(school_name="X")

⚡ PERSON_TYPE — ประเภทบุคลากร (สำคัญมาก!):
- "ข้าราชการครู"/"ข้าราชการ" → person_type="ข้าราชการครู"
- "ลูกจ้างชั่วคราว"/"ครูอัตราจ้าง"/"ครูจ้าง" → person_type="ลูกจ้างชั่วคราว"
- "พนักงานราชการ"/"พนง.ราชการ" → person_type="พนักงานราชการ"
- "ลูกจ้างประจำ" → person_type="ลูกจ้างประจำ"
- ⚠️ ถ้าถาม "มีข้าราชการครูกี่คน" → count_teachers(person_type="ข้าราชการครู")
- ⚠️ ถ้าถาม "โรงเรียน X มีครูอัตราจ้างกี่คน" → count_teachers(school_name="X", person_type="ลูกจ้างชั่วคราว")
- ⚠️ ถ้าถามแค่ "ครูกี่คน" โดยไม่ระบุประเภท → count_teachers() ไม่ต้องใส่ person_type
- ⚠️ ถ้าให้จัดอันดับ (ranking) ครูตามประเภท ให้ส่ง person_type ไปใน parameter ของ tool `ranking` ด้วย (เช่น "จังหวัดไหนมีครูอัตราจ้างมากสุด" -> ranking(metric="teachers", person_type="ลูกจ้างชั่วคราว", scope="province"))

แนวทาง multi-step:
- ถ้าคำถามต้อง "คำนวณเฉลี่ย" หรือ "ต่อโรงเรียน" ให้สร้าง multi_step
  ตัวอย่าง: "เฉลี่ยจำนวนครูต่อโรงเรียนของภาคใต้"
  ขั้นตอน:
  1) count_teachers(region=ภาคใต้) save_as=teachers
  2) count_schools(region=ภาคใต้) save_as=schools
  3) derive: divide teachers.total_teachers / schools.total_schools

ตอบเป็น JSON object เท่านั้น ตาม schema นี้:
{{
  "tool": "tool_name or null",
  "params": {{ }},
  "intent": "optional_intent_or_null",
  "confidence": 0.0,
  "data_required": true/false,
  "data_reason": "short reason or null",
  "multi_step": {{
    "steps": [
      {{"tool": "tool_name", "params": {{}}, "save_as": "alias"}}
    ],
    "derive": {{
      "operation": "divide|ratio|average",
      "numerator": {{"step": "alias", "field": "total_teachers|total_students|total_schools|..."}},
      "denominator": {{"step": "alias", "field": "total_teachers|total_students|total_schools|..."}},
      "precision": 2,
      "label": "คำอธิบายสั้นๆ",
      "unit": "หน่วย"
    }}
  }},
  "needs_clarification": true/false,
  "clarification_question": "string or null"
}}
"""

    try:
        response = llm_client.generate_content(prompt, timeout=30)
        response_text = (response.text or "").strip()

        # Strip code fences if present
        if "```" in response_text:
            response_text = response_text.replace("```json", "```")
            response_text = response_text.split("```")[1].strip()

        # Extract JSON object
        try:
            raw = json.loads(response_text)
        except json.JSONDecodeError:
            # Fallback: find first JSON object in text
            start = response_text.find("{")
            end = response_text.rfind("}")
            if start >= 0 and end > start:
                raw = json.loads(response_text[start:end + 1])
            else:
                raise

        tool = raw.get("tool")
        params = raw.get("params") if isinstance(raw.get("params"), dict) else {}
        needs_clarification = bool(raw.get("needs_clarification"))
        clarification_question = raw.get("clarification_question")
        confidence = raw.get("confidence")
        intent = raw.get("intent")
        multi_step = raw.get("multi_step") if isinstance(raw.get("multi_step"), dict) else None
        data_required = raw.get("data_required")
        data_reason = raw.get("data_reason")

        # Normalize/validate key params
        raw_province = params.get("province")
        raw_region = params.get("region")

        norm_province = _normalize_province(raw_province) if raw_province else None
        norm_region = _normalize_region(raw_region) if raw_region else None

        # If province was actually a region name (common LLM slip), promote it
        if not norm_province and raw_province:
            norm_region_from_prov = _normalize_region(raw_province)
            if norm_region_from_prov:
                norm_region = norm_region_from_prov

        params["province"] = norm_province
        params["region"] = norm_region

        if params.get("province") and params.get("region"):
            # Province is more specific; drop region to avoid conflict
            params.pop("region", None)

        params["gender"] = _normalize_gender(params.get("gender"))

        # Fetch valid values only when needed (avoid heavy Qdrant calls for general chat)
        needs_valid_values = (
            tool not in [None, "general_chat"]
            and data_required is not False
            and (
                any(params.get(k) for k in ["agency", "district", "area_name", "person_type", "grade"])
                or tool in ["search_education_areas", "get_education_area_info", "analyze_teacher_distribution", "count_by_system_type"]
            )
        )
        valid_values = fetch_valid_values() if needs_valid_values else {}
        if not valid_values:
            valid_values = {'person_type': [], 'grade': [], 'agency': [], 'area_name': [], 'district': []}

        # Normalize agency (prefer canonical short code)
        if "agency" in params:
            params["agency"] = _normalize_agency(params.get("agency"), valid_values.get("agency", []))

        # Coerce numeric fields
        for key in ["limit", "min_students", "max_students", "min_teachers", "max_teachers", "value", "radius_km"]:
            if key in params:
                params[key] = _coerce_int(params.get(key))

        # ✨ Year normalization (e.g. "67" -> "2567")
        raw_year = params.get("year")
        if raw_year:
            year_str = str(raw_year).strip()
            if year_str in YEAR_ALIASES:
                params["year"] = YEAR_ALIASES[year_str]
            elif len(year_str) == 2 and year_str.isdigit():
                params["year"] = f"25{year_str}"
        else:
            # Safety net: Regex-based year detection from question text
            year_match = re.search(r'(?:ปี|พ\.?ศ\.?)\s*(25)?(\d{2})(?!\d)', question)
            if year_match:
                short = year_match.group(2)
                detected_year = f"25{short}"
                params["year"] = detected_year
                logger.info(f"📅 Auto-detected year from question: {detected_year}")

        # Validate/normalize district/area/person_type/grade against known values when possible
        if "district" in params:
            params["district"] = _normalize_district(params.get("district"), valid_values.get("district", []), params.get("province"))
        if "area_name" in params:
            params["area_name"] = _normalize_area_name(params.get("area_name"), valid_values.get("area_name", []))
        if "person_type" in params:
            params["person_type"] = _match_valid_value(params.get("person_type"), valid_values.get("person_type", [])) or params.get("person_type")
        if "grade" in params:
            params["grade"] = _normalize_grade(params.get("grade"), valid_values.get("grade", []))
        if "grade" in params:
            params["grade"] = params.get("grade")

        # Normalize compare_provinces provinces list
        if tool == "compare_provinces":
            provinces = params.get("provinces")
            if isinstance(provinces, str):
                provinces = [p.strip() for p in provinces.replace(";", ",").split(",") if p.strip()]
            if isinstance(provinces, list):
                cleaned = []
                for p in provinces:
                    norm = _normalize_province(p)
                    if norm:
                        cleaned.append(norm)
                params["provinces"] = cleaned

        # Confidence normalization
        try:
            confidence = float(confidence) if confidence is not None else None
        except Exception:
            confidence = None
        if confidence is None:
            confidence = 0.6 if tool or multi_step else 0.2
        confidence = max(0.0, min(1.0, confidence))

        # data_required normalization (fallback to tool presence)
        if data_required is None:
            data_required = bool(tool and tool != "general_chat") or bool(multi_step)
        data_required = bool(data_required)

        return {
            "tool": tool,
            "params": params,
            "intent": intent,
            "confidence": confidence,
            "data_required": data_required,
            "data_reason": data_reason,
            "multi_step": multi_step,
            "needs_clarification": needs_clarification,
            "clarification_question": clarification_question
        }

    except json.JSONDecodeError as e:
        logger.warning(f"⚠️ Structured extraction failed (JSON Parse Error): {e}")
        return {
            "tool": None,
            "params": {},
            "intent": None,
            "confidence": 0.2,
            "data_required": False,
            "data_reason": None,
            "multi_step": None,
            "needs_clarification": True,
            "clarification_question": "ขอรายละเอียดเพิ่มอีกนิดได้ไหมครับ เช่น จังหวัด/โรงเรียน/ประเภทข้อมูลที่ต้องการ"
        }
    except Exception as e:
        import traceback
        logger.error(f"❌ Structured extraction failed (System Error):\n{traceback.format_exc()}")
        return {
            "tool": None,
            "params": {},
            "intent": None,
            "confidence": 0.2,
            "data_required": False,
            "data_reason": None,
            "multi_step": None,
            "needs_clarification": True,
            "clarification_question": "ขออภัยครับ ระบบประมวลผลคำถามขัดข้องชั่วคราว กรุณาลองใหม่อีกครั้ง"
        }


def _get_qdrant_client() -> QdrantClient:
    """Get Qdrant client instance"""
    qdrant_url = os.getenv("QDRANT_URL", "http://203.159.242.144:6333")
    qdrant_timeout = int(os.getenv("VALID_VALUES_QDRANT_TIMEOUT", os.getenv("QDRANT_TIMEOUT", "5")))
    return QdrantClient(url=qdrant_url, timeout=qdrant_timeout)


def fetch_valid_values() -> Dict[str, List[str]]:
    """
    ดึงค่าที่ถูกต้องทั้งหมดจาก Qdrant เพื่อใช้เป็น reference
    เรียกครั้งเดียวตอน startup แล้ว cache ไว้
    """
    global _VALID_VALUES_CACHE, _VALID_VALUES_LAST_FAIL, _VALID_VALUES_LAST_SUCCESS
    
    if _VALID_VALUES_CACHE:
        return _VALID_VALUES_CACHE

    if not ENABLE_VALID_VALUES_FETCH:
        return {'person_type': [], 'grade': [], 'agency': [], 'area_name': [], 'district': []}

    # Circuit breaker: avoid repeated timeouts
    now = time.time()
    if _VALID_VALUES_LAST_FAIL and (now - _VALID_VALUES_LAST_FAIL) < VALID_VALUES_RETRY_SECONDS:
        return {'person_type': [], 'grade': [], 'agency': [], 'area_name': [], 'district': []}
    
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
        _VALID_VALUES_LAST_SUCCESS = time.time()
        logger.info(f"✅ Loaded valid values: {len(person_types)} person_types, {len(grades)} grades, {len(agencies)} agencies, {len(area_names)} areas, {len(districts)} districts")
        return _VALID_VALUES_CACHE
    
    except Exception as e:
        _VALID_VALUES_LAST_FAIL = time.time()
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
