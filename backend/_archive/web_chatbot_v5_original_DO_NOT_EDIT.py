"""
web_chatbot_v5.py - Production-Ready Smart Education Chatbot

🎯 Version 5.0 (Production)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ FEATURES:
- Two-Word Smart Parsing (ดอยลาน เมืองเชียงราย → ทำงานได้!)
- Single Word Listing (เวียง → แสดง list ทั้งหมด)
- Drill-down Support (เวียง เชียงแสน → ระบุเจาะจง)
- Enhanced Search Strategy (3-level fallback)
- Better Error Messages (แนะนำวิธีถามที่ดีกว่า)
- ✨ NEW: Full Comparison Support (มากที่สุด/น้อยที่สุด)
- ✨ NEW: Region-based queries (ภาคใต้/ภาคเหนือ)
- ✨ NEW: Production-grade error handling
- ✨ NEW: Connection pooling & retry logic

💡 QUERY TYPES SUPPORTED:
- Count: "ปัตตานีมีกี่โรงเรียน"
- Ranking (Most): "อำเภอไหนมีโรงเรียนมากที่สุด"
- Ranking (Least): "อำเภอไหนมีโรงเรียนน้อยที่สุด"
- Comparison: "เปรียบเทียบ ปัตตานี กับ ยะลา"
- Search: "ตำบลบานา อำเภอเมืองปัตตานี"
- Region: "ภาคใต้มีกี่โรงเรียน"

Author: DO-MOE Education Team
Version: 5.0.0 (Production)
Last Updated: 2026-01-09
"""

import os
import re
import time
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Generator, Any
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from collections import defaultdict
from difflib import SequenceMatcher

# Third-party imports
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, VectorParams, Distance, PointStruct
import google.generativeai as genai
import session_db  # Session Persistence

# Initialize Session DB
try:
    session_db.init_db()
except Exception as e:
    logging.error(f"Failed to init Session DB: {e}")

try:
    import gradio as gr
    GRADIO_AVAILABLE = True
except ImportError:
    print("⚠️ Gradio not installed. Install: pip install gradio")
    GRADIO_AVAILABLE = False


# =====================================================================
# LOGGING CONFIGURATION
# =====================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# =====================================================================
# CONFIGURATION
# =====================================================================
current_dir = Path(__file__).parent
load_dotenv(dotenv_path=current_dir / ".env")

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
QDRANT_URL = os.getenv("QDRANT_URL", "http://203.159.242.144:6333")
QDRANT_TIMEOUT = int(os.getenv("QDRANT_TIMEOUT", "60"))

# Initialize Gemini (Fallback)
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info("✅ Gemini API configured (Fallback)")
else:
    logger.warning("⚠️ GEMINI_API_KEY not found")

# Initialize Groq (Primary)
if GROQ_API_KEY and GROQ_API_KEY != "your_groq_api_key_here":
    logger.info(f"✅ Groq API configured (Primary) - Model: {GROQ_MODEL}")
else:
    logger.warning("⚠️ GROQ_API_KEY not found - Using Gemini only")



class MultiProviderLLM:
    """
    Multi-provider LLM wrapper with automatic fallback:
    1. Groq (Primary) - Faster, generous free tier
    2. Gemini (Fallback) - When Groq fails
    
    API keys are fetched from Firestore (Admin Panel config) for consistency.
    Falls back to .env if Firestore is unavailable.
    """
    
    def __init__(self, category: str = "school", gemini_model: str = 'gemini-2.0-flash-exp'):
        self.category = category
        self.groq_model = GROQ_MODEL
        self.gemini_model_name = gemini_model
        self.gemini_model = None
        
        # Try to load keys from Firestore first
        self._load_keys_from_firestore()
        
        self._init_gemini(gemini_model)
    
    def _load_keys_from_firestore(self):
        """Load API keys from Firestore (synced with Admin Panel)"""
        try:
            from firebase_config import get_groq_key, get_gemini_key
            
            # Get keys from Firestore
            self.groq_key = get_groq_key(self.category)
            firestore_gemini_key = get_gemini_key(self.category)
            
            if self.groq_key:
                logger.info(f"✅ Groq key loaded from Firestore (category: {self.category})")
            else:
                # Fallback to .env
                self.groq_key = GROQ_API_KEY
                if self.groq_key and self.groq_key != "your_groq_api_key_here":
                    logger.info("✅ Groq key loaded from .env")
            
            if firestore_gemini_key:
                # Configure Gemini with Firestore key
                genai.configure(api_key=firestore_gemini_key)
                logger.info(f"✅ Gemini key loaded from Firestore (category: {self.category})")
                
        except ImportError:
            logger.warning("⚠️ firebase_config not available, using .env fallback")
            self.groq_key = GROQ_API_KEY
        except Exception as e:
            logger.warning(f"⚠️ Firestore config load failed: {e}")
            self.groq_key = GROQ_API_KEY
        
    def _init_gemini(self, model_name: str):
        """Initialize Gemini as fallback"""
        try:
            if not model_name.startswith('models/'):
                model_name = f'models/{model_name}'
            self.gemini_model = genai.GenerativeModel(model_name)
            logger.info(f"✅ Gemini fallback ready: {model_name}")
        except Exception as e:
            logger.error(f"Failed to init Gemini: {e}")
    
    def generate_content(self, prompt: str, timeout: int = 30) -> 'LLMResponse':
        """Generate content using Groq first, then Gemini as fallback"""
        
        # Try Groq first (if configured)
        if self.groq_key and self.groq_key != "your_groq_api_key_here":
            try:
                response = self._call_groq(prompt, timeout)
                if response:
                    return LLMResponse(text=response, provider="groq")
            except Exception as e:
                logger.warning(f"⚠️ Groq failed, falling back to Gemini: {e}")
        
        # Fallback to Gemini
        try:
            if self.gemini_model:
                response = self.gemini_model.generate_content(prompt)
                return LLMResponse(text=response.text, provider="gemini")
        except Exception as e:
            logger.error(f"❌ Gemini fallback also failed: {e}")
            raise
    
    def _call_groq(self, prompt: str, timeout: int = 30) -> Optional[str]:
        """Call Groq API"""
        import requests
        
        headers = {
            "Authorization": f"Bearer {self.groq_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.groq_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2048,
            "temperature": 0.7
        }
        
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=timeout
        )
        
        if response.status_code == 200:
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            logger.info(f"⚡ Groq responded ({self.groq_model})")
            return content
        elif response.status_code == 429:
            logger.warning(f"⚠️ Groq rate limited (429)")
            return None
        else:
            logger.warning(f"⚠️ Groq error: {response.status_code}")
            return None


@dataclass
class LLMResponse:
    """LLM Response wrapper"""
    text: str
    provider: str = "unknown"


# Qdrant Client with connection pooling
qdrant_client = QdrantClient(
    url=QDRANT_URL,
    timeout=QDRANT_TIMEOUT,
    prefer_grpc=False
)

# Collections
COLLECTIONS = {
    "province": "education_statistics_province",
    "district": "education_statistics_district",
    "subdistrict": "education_statistics_subdistrict",
    "agency": "education_statistics_agency",
    "schools": "education_schools"
}


# =====================================================================
# INPUT SANITIZATION & SECURITY
# =====================================================================
class InputSanitizer:
    """Security layer for input validation and sanitization"""
    
    # Configuration
    MAX_LENGTH = 1000
    MIN_LENGTH = 1
    
    # Common prompt injection patterns
    INJECTION_PATTERNS = [
        r"ignore\s*(all\s*)?(previous|above)\s*(instructions?|prompts?)",
        r"forget\s*(everything|all|your)\s*(you|instructions?)?",
        r"you\s*are\s*(now|a)\s*(new|different|evil)",
        r"pretend\s*(to\s*be|you\s*are)",
        r"disregard\s*(all|previous|your)",
        r"override\s*(your|the)\s*(instructions?|programming)",
        r"jailbreak",
        r"DAN\s*mode",
        r"\[system\]",
        r"\[INST\]",
        r"<\|.*?\|>",
    ]
    
    def __init__(self):
        self.injection_regex = re.compile(
            '|'.join(self.INJECTION_PATTERNS), 
            re.IGNORECASE
        )
    
    def sanitize(self, query: str) -> Tuple[str, Optional[str]]:
        """
        Sanitize user input.
        Returns: (sanitized_query, error_message)
        If error_message is not None, the input should be rejected.
        """
        if not query:
            return "", "❌ กรุณาพิมพ์ข้อความครับ"
        
        # Strip whitespace
        query = query.strip()
        
        # Check minimum length
        if len(query) < self.MIN_LENGTH:
            return "", "❌ กรุณาพิมพ์ข้อความครับ"
        
        # Check maximum length
        if len(query) > self.MAX_LENGTH:
            return "", f"❌ ข้อความยาวเกินไป (สูงสุด {self.MAX_LENGTH} ตัวอักษร)"
        
        # Detect prompt injection
        if self.detect_injection(query):
            logger.warning(f"🚨 Prompt injection attempt detected: {query[:50]}...")
            return "", "🛡️ ขออภัยครับ ข้อความนี้ไม่สามารถประมวลผลได้ กรุณาถามใหม่อีกครั้งครับ"
        
        # Basic sanitization: remove control characters
        query = ''.join(char for char in query if ord(char) >= 32 or char in '\n\t')
        
        return query, None
    
    def detect_injection(self, query: str) -> bool:
        """Detect common prompt injection patterns"""
        return bool(self.injection_regex.search(query))
    
    @staticmethod
    def escape_html(text: str) -> str:
        """Escape HTML entities to prevent XSS"""
        if not text:
            return text
        html_escape_table = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#x27;",
        }
        for char, escaped in html_escape_table.items():
            text = text.replace(char, escaped)
        return text


# Global sanitizer instance
input_sanitizer = InputSanitizer()


# =====================================================================
# ENUMS & DATA CLASSES
# =====================================================================
class QueryIntent(Enum):
    COUNT = "count"
    RANKING_MOST = "ranking_most"
    RANKING_LEAST = "ranking_least"
    COMPARE = "compare"
    SEARCH = "search"
    LIST = "list"
    SCHOOL_SEARCH = "school_search"
    SCHOOL_LIST = "school_list"
    SCHOOL_DETAIL = "school_detail"
    LOAD_MORE = "load_more"  # Pagination - load more results
    SCHOOL_COUNT = "school_count"
    UNKNOWN = "unknown"


class QueryLevel(Enum):
    PROVINCE = "province"
    DISTRICT = "district"
    SUBDISTRICT = "subdistrict"
    AGENCY = "agency"


@dataclass
class ParsedQuery:
    """Structured query result"""
    intent: QueryIntent
    level: QueryLevel
    province: Optional[str] = None
    district: Optional[str] = None
    subdistrict: Optional[str] = None
    agency: Optional[str] = None
    region: Optional[str] = None
    school_name: Optional[str] = None  # Added for LLM extraction
    original_query: str = ""
    normalized_query: str = ""
    confidence: float = 0.0


@dataclass
class SearchResult:
    """Search result container"""
    data: List[Tuple[str, Dict]]
    count: int
    is_least: bool = False
    source: str = ""
    search_time_ms: float = 0


# =====================================================================
# THAI LANGUAGE DATA
# =====================================================================
THAI_PROVINCES = [
    'กรุงเทพมหานคร', 'กระบี่', 'กาญจนบุรี', 'กาฬสินธุ์', 'กำแพงเพชร', 'ขอนแก่น', 
    'จันทบุรี', 'ฉะเชิงเทรา', 'ชลบุรี', 'ชัยนาท', 'ชัยภูมิ', 'ชุมพร', 'ตรัง', 'ตราด', 
    'ตาก', 'นครนายก', 'นครปฐม', 'นครพนม', 'นครราชสีมา', 'นครศรีธรรมราช', 'นครสวรรค์', 
    'นนทบุรี', 'นราธิวาส', 'น่าน', 'บึงกาฬ', 'บุรีรัมย์', 'ปทุมธานี', 'ประจวบคีรีขันธ์', 
    'ปราจีนบุรี', 'ปัตตานี', 'พระนครศรีอยุธยา', 'พะเยา', 'พังงา', 'พัทลุง', 'พิจิตร', 
    'พิษณุโลก', 'ภูเก็ต', 'มหาสารคาม', 'มุกดาหาร', 'ยะลา', 'ยโสธร', 'ร้อยเอ็ด', 
    'ระนอง', 'ระยอง', 'ราชบุรี', 'ลพบุรี', 'ลำปาง', 'ลำพูน', 'ศรีสะเกษ', 'สกลนคร', 
    'สงขลา', 'สตูล', 'สมุทรปราการ', 'สมุทรสงคราม', 'สมุทรสาคร', 'สระแก้ว', 'สระบุรี', 
    'สิงห์บุรี', 'สุโขทัย', 'สุพรรณบุรี', 'สุราษฎร์ธานี', 'สุรินทร์', 'หนองคาย', 
    'หนองบัวลำภู', 'อ่างทอง', 'อำนาจเจริญ', 'อุดรธานี', 'อุตรดิตถ์', 'อุทัยธานี', 
    'อุบลราชธานี', 'เชียงราย', 'เชียงใหม่', 'เพชรบุรี', 'เพชรบูรณ์', 'เลย', 'แพร่', 
    'แม่ฮ่องสอน'
]

PROVINCE_ALIASES = {
    'กทม': 'กรุงเทพมหานคร', 'กทม.': 'กรุงเทพมหานคร', 'กรุงเทพฯ': 'กรุงเทพมหานคร',
    'โคราช': 'นครราชสีมา', 'อุดร': 'อุดรธานี', 'อุบล': 'อุบลราชธานี',
    'นครศรี': 'นครศรีธรรมราช', 'ปัตาานี': 'ปัตตานี', 'ปัตานี': 'ปัตตานี',
}

AGENCY_ALIASES = {
    'สพฐ': 'สำนักงานคณะกรรมการการศึกษาขั้นพื้นฐาน',
    'สพฐ.': 'สำนักงานคณะกรรมการการศึกษาขั้นพื้นฐาน',
    'เอกชน': 'สำนักงานคณะกรรมการส่งเสริมการศึกษาเอกชน',
    'สช': 'สำนักงานคณะกรรมการส่งเสริมการศึกษาเอกชน',
    'สช.': 'สำนักงานคณะกรรมการส่งเสริมการศึกษาเอกชน',
    'อปท': 'กรมส่งเสริมการปกครองท้องถิ่น',
    'อปท.': 'กรมส่งเสริมการปกครองท้องถิ่น',
    'ท้องถิ่น': 'กรมส่งเสริมการปกครองท้องถิ่น',
    'สอศ': 'สำนักงานคณะกรรมการการอาชีวศึกษา',
    'สอศ.': 'สำนักงานคณะกรรมการการอาชีวศึกษา',
    'อาชีวะ': 'สำนักงานคณะกรรมการการอาชีวศึกษา',
}

# Region mapping
REGIONS = {
    'ภาคเหนือ': ['เชียงใหม่', 'เชียงราย', 'ลำปาง', 'ลำพูน', 'แม่ฮ่องสอน', 'พะเยา', 'แพร่', 'น่าน', 'อุตรดิตถ์'],
    'ภาคตะวันออกเฉียงเหนือ': ['นครราชสีมา', 'ขอนแก่น', 'อุดรธานี', 'อุบลราชธานี', 'บุรีรัมย์', 'สุรินทร์', 
                              'ศรีสะเกษ', 'ร้อยเอ็ด', 'มหาสารคาม', 'กาฬสินธุ์', 'สกลนคร', 'นครพนม', 'มุกดาหาร',
                              'ยโสธร', 'อำนาจเจริญ', 'หนองคาย', 'หนองบัวลำภู', 'บึงกาฬ', 'ชัยภูมิ', 'เลย'],
    'ภาคอีสาน': ['นครราชสีมา', 'ขอนแก่น', 'อุดรธานี', 'อุบลราชธานี'],  # Alias
    'ภาคกลาง': ['กรุงเทพมหานคร', 'นนทบุรี', 'ปทุมธานี', 'สมุทรปราการ', 'พระนครศรีอยุธยา', 'สระบุรี',
                'ลพบุรี', 'สิงห์บุรี', 'อ่างทอง', 'ชัยนาท', 'นครนายก', 'ปราจีนบุรี', 'นครปฐม', 
                'สุพรรณบุรี', 'นครสวรรค์', 'อุทัยธานี', 'กำแพงเพชร', 'พิจิตร', 'พิษณุโลก', 'สุโขทัย', 'เพชรบูรณ์'],
    'ภาคตะวันออก': ['ชลบุรี', 'ระยอง', 'จันทบุรี', 'ตราด', 'ฉะเชิงเทรา', 'สระแก้ว'],
    'ภาคตะวันตก': ['กาญจนบุรี', 'ราชบุรี', 'สมุทรสาคร', 'สมุทรสงคราม', 'เพชรบุรี', 'ประจวบคีรีขันธ์', 'ตาก'],
    'ภาคใต้': ['สุราษฎร์ธานี', 'นครศรีธรรมราช', 'สงขลา', 'ปัตตานี', 'ยะลา', 'นราธิวาส', 'พัทลุง', 
               'สตูล', 'ตรัง', 'กระบี่', 'พังงา', 'ภูเก็ต', 'ระนอง', 'ชุมพร']
}


# =====================================================================
# INTENT DETECTION KEYWORDS
# =====================================================================
INTENT_KEYWORDS = {
    QueryIntent.RANKING_MOST: [
        'มากที่สุด', 'เยอะที่สุด', 'สูงสุด', 'มากสุด', 'เยอะสุด', 
        'ที่สุด', 'อันดับ 1', 'อันดับหนึ่ง', 'อันดับแรก', 'top'
    ],
    QueryIntent.RANKING_LEAST: [
        'น้อยที่สุด', 'น้อยสุด', 'ต่ำสุด', 'น้อยกว่า', 'ต่ำที่สุด',
        'อันดับท้าย', 'อันดับสุดท้าย', 'รั้งท้าย'
    ],
    QueryIntent.COMPARE: [
        'เปรียบเทียบ', 'เทียบ', 'เทียบกับ', 'vs', 'versus', 'กับ',
        'มากกว่า', 'น้อยกว่า', 'แตกต่าง', 'ต่างกัน'
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

# =====================================================================
# LLM-BASED INTENT CLASSIFIER (INTELLIGENT)
# =====================================================================
class LLMIntentClassifier:
    """🧠 Uses LLM to classify user intent intelligently"""
    
    CLASSIFICATION_PROMPT = '''คุณเป็น AI จำแนกประเภทคำถามเกี่ยวกับการศึกษาไทย
ตอบเป็น JSON เท่านั้น ห้ามมีข้อความอื่น

ประเภทคำถาม (intent):
- SCHOOL_COUNT: ถามจำนวนโรงเรียน เช่น "มีกี่โรง", "กี่โรงเรียน", "จำนวนเท่าไหร่"
- SCHOOL_LIST: ขอรายชื่อโรงเรียน เช่น "รายชื่อโรงเรียน", "โรงเรียนใน", "มีโรงเรียนอะไรบ้าง"
- SCHOOL_DETAIL: ขอข้อมูลโรงเรียนเฉพาะ เช่น "ข้อมูลโรงเรียน...", "โรงเรียน...อยู่ที่ไหน", "เบอร์โทรโรงเรียน..."
- SCHOOL_SEARCH: ค้นหาโรงเรียนจากชื่อบางส่วน เช่น "หาโรงเรียน...", "ค้นหาโรงเรียน..."
- RANKING_MOST: อันดับมากที่สุด เช่น "จังหวัดไหนมีมากที่สุด", "อันดับ 1"
- RANKING_LEAST: อันดับน้อยที่สุด เช่น "จังหวัดไหนมีน้อยที่สุด"
- LOAD_MORE: ดูเพิ่ม เช่น "ดูเพิ่มเติม", "ดูต่อ", "ถัดไป"
- GENERAL: คำถามทั่วไปที่ไม่เข้าข้างต้น

ภูมิภาคที่รองรับ: ภาคเหนือ, ภาคใต้, ภาคกลาง, ภาคตะวันออก, ภาคตะวันตก, ภาคตะวันออกเฉียงเหนือ, ภาคอีสาน
สังกัด: สพฐ (สำนักงานคณะกรรมการการศึกษาขั้นพื้นฐาน), เอกชน, อปท, สอศ

ตอบ JSON:
{"intent": "...", "region": "..." หรือ null, "province": "..." หรือ null, "district": "..." หรือ null, "agency": "..." หรือ null, "school_name": "..." หรือ null}

คำถาม: '''

    def __init__(self, model=None):
        self.model = model
        self.llm = MultiProviderLLM(category="school")  # Uses Groq primary, Gemini fallback
        
    def classify(self, query: str) -> dict:
        """Classify user intent using LLM (Groq primary, Gemini fallback)"""
        import json
        try:
            prompt = self.CLASSIFICATION_PROMPT + query
            
            # Use MultiProviderLLM (Groq -> Gemini fallback)
            llm_response = self.llm.generate_content(prompt)
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
                
                logger.info(f"🧠 LLM Intent (Groq/Gemini): {result}")
                return result
                
        except Exception as e:
            logger.warning(f"⚠️ LLM classification failed: {e}")
            
        # Return None to indicate fallback to keyword matching
        return None


# =====================================================================
# RESPONSE SYNTHESIZER (CHATGPT-QUALITY RESPONSES)
# =====================================================================
class ResponseSynthesizer:
    """🎯 Generates comprehensive, ChatGPT-quality responses from database results"""
    
    SYNTHESIS_PROMPT = '''คุณเป็น AI ชื่อ "DO AI" ผู้เชี่ยวชาญด้านการศึกษาไทย

⚠️ กฎสำคัญที่สุด (ห้ามละเมิด!):
1. ใช้เฉพาะข้อมูลที่ให้มาใน JSON เท่านั้น
2. ห้ามแต่งชื่อโรงเรียน ห้ามแต่งตัวเลข ห้ามแต่งข้อมูลใดๆ ที่ไม่มีใน JSON
3. ถ้าไม่มีข้อมูล ให้บอกว่า "ไม่มีข้อมูล"
4. ชื่อโรงเรียนต้องตรงกับที่ให้มา 100%

กฎการตอบ:
- ใช้ภาษาไทยที่เป็นมิตร
- จัดโครงสร้างด้วย emoji และ bullet points
- สรุปภาพรวมก่อน แล้วลงรายละเอียด
- ตอบ markdown format
- เพิ่มคำถามต่อไป (follow-up) ที่ท้าย

โครงสร้างคำตอบ:
📊 **[หัวข้อสรุป]**
[สรุปจากข้อมูล JSON]

🏫 **รายละเอียด**
[ข้อมูลจาก JSON เท่านั้น]

💡 **คำถามที่น่าสนใจ**
- [คำถาม 1]
- [คำถาม 2]

---
✅ ข้อมูลจาก DO-Moe Education Database (Real-time)

ข้อมูลจาก Database (ใช้เฉพาะข้อมูลนี้เท่านั้น!):
'''

    def __init__(self):
        self.llm = MultiProviderLLM(category="school")  # Uses Groq primary, Gemini fallback

    def synthesize(self, intent: str, data: dict, query: str) -> str:
        """Generate comprehensive response using LLM (Groq primary, Gemini fallback)"""
        import json  # Local import to avoid issues
        try:
            # Build context from data
            context = f"คำถามผู้ใช้: {query}\n"
            context += f"ประเภทคำถาม: {intent}\n"
            context += f"ข้อมูล:\n{json.dumps(data, ensure_ascii=False, indent=2)}\n"
            
            prompt = self.SYNTHESIS_PROMPT + context
            
            # Use MultiProviderLLM (Groq -> Gemini fallback)
            llm_response = self.llm.generate_content(prompt)
            result = llm_response.text if llm_response else None
            
            if result:
                logger.info(f"✨ Response synthesized successfully (Groq/Gemini)")
                return result
                
        except Exception as e:
            logger.warning(f"⚠️ Response synthesis failed: {e}")
            
        return None


# =====================================================================
# SMART QUERY PARSER (V5 - PRODUCTION)
# =====================================================================
class SmartQueryParser:
    """🧠 Production-Ready Smart Query Parser with LLM Intelligence"""
    
    def __init__(self):
        self._province_cache = {p.lower(): p for p in THAI_PROVINCES}
        self._alias_cache = {k.lower(): v for k, v in PROVINCE_ALIASES.items()}
        self.llm_classifier = LLMIntentClassifier()  # LLM-based classification
        
    def normalize_query(self, query: str) -> str:
        """Normalize query by adding spaces and cleaning"""
        # Add space after keywords
        query = re.sub(r'(ตำบล|แขวง|อำเภอ|เขต|จังหวัด|ต\.|อ\.|จ\.)', r'\1 ', query)
        # Remove duplicate spaces
        query = re.sub(r'\s+', ' ', query)
        return query.strip()
    
    def detect_intent(self, query: str) -> QueryIntent:
        """Detect query intent from keywords"""
        query_lower = query.lower()
        
        # ============================================================
        # RANKING INTENTS - CHECK FIRST (Before school queries!)
        # Queries like "ภาคใต้จังหวัดไหนมีโรงเรียนมากที่สุด" should be
        # detected as RANKING, not SCHOOL_SEARCH
        # ============================================================
        
        # Check "น้อยที่สุด" first (more specific)
        least_keywords = INTENT_KEYWORDS[QueryIntent.RANKING_LEAST]
        if any(kw in query_lower for kw in least_keywords):
            return QueryIntent.RANKING_LEAST
        
        # Check "มากที่สุด" second
        most_keywords = INTENT_KEYWORDS[QueryIntent.RANKING_MOST]
        if any(kw in query_lower for kw in most_keywords):
            return QueryIntent.RANKING_MOST
        
        # ============================================================
        # SCHOOL-SPECIFIC INTENTS (After ranking check)
        # ============================================================
        # Check for school detail queries (most specific)
        school_detail_kw = INTENT_KEYWORDS.get(QueryIntent.SCHOOL_DETAIL, [])
        if any(kw in query_lower for kw in school_detail_kw):
            return QueryIntent.SCHOOL_DETAIL
        
        # Check for school count queries
        school_count_kw = INTENT_KEYWORDS.get(QueryIntent.SCHOOL_COUNT, [])
        if any(kw in query_lower for kw in school_count_kw):
            return QueryIntent.SCHOOL_COUNT
        
        # Check for school list queries (โรงเรียนใน... มีอะไรบ้าง)
        school_list_kw = INTENT_KEYWORDS.get(QueryIntent.SCHOOL_LIST, [])
        if any(kw in query_lower for kw in school_list_kw):
            return QueryIntent.SCHOOL_LIST
        
        # Check for general school search (โรงเรียน + ชื่อ)
        school_search_kw = INTENT_KEYWORDS.get(QueryIntent.SCHOOL_SEARCH, [])
        if any(kw in query_lower for kw in school_search_kw):
            # If just "โรงเรียน" + province, it's a list
            if any(p.lower() in query_lower for p in THAI_PROVINCES):
                return QueryIntent.SCHOOL_LIST
            return QueryIntent.SCHOOL_SEARCH
        
        # Check other intents
        for intent in [QueryIntent.COMPARE, QueryIntent.COUNT, QueryIntent.LIST]:
            keywords = INTENT_KEYWORDS.get(intent, [])
            if any(kw in query_lower for kw in keywords):
                return intent
        
        # Default: if asking about location, it's a search
        if any(kw in query_lower for kw in ['ตำบล', 'อำเภอ', 'จังหวัด', 'เขต', 'แขวง']):
            return QueryIntent.COUNT
        
        return QueryIntent.SEARCH
    
    def detect_region(self, query: str) -> Optional[str]:
        """Detect region from query"""
        query_lower = query.lower()
        
        # Keywords that imply "all regions" / "each region"
        each_region_keywords = [
            'แต่ละภาค', 'ทุกภาค', 'สรุปภาค', 'รายภาค',
            'ภาคไหน', 'ภาค ไหน', 'ภาคใด', 'ภาค ใด',  # "Which region?"
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
        
        # Check full names
        for province in THAI_PROVINCES:
            if province.lower() in query_lower:
                return province
        
        # Check aliases
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
        
        # Detect region
        entities['region'] = self.detect_region(query)
        
        # Detect province
        entities['province'] = self.detect_province(query)
        
        # Auto-detect Bangkok
        if not entities['province'] and self.detect_bangkok(query):
            entities['province'] = 'กรุงเทพมหานคร'
        
        # Clean query for further parsing
        cleaned = normalized
        noise_words = [
            'มี', 'กี่', 'โรง', 'โรงเรียน', 'แห่ง', 'เท่าไหร่', 'ทำไหร่', 
            'จำนวน', 'ทั้งหมด', 'บ้าง', 'ครับ', 'ค่ะ', 'คะ', 'เรียน',
            'ของ', 'ใน', 'ที่', 'ซึ่ง', 'มากที่สุด', 'น้อยที่สุด',
            'เยอะที่สุด', 'น้อยสุด', 'มากสุด', 'อันดับ'
        ]
        for word in noise_words:
            cleaned = cleaned.replace(word, ' ')
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Extract district/subdistrict with patterns
        # Pattern: ตำบล X อำเภอ Y
        combined_match = re.search(
            r'(?:ตำบล|แขวง|ต\.)\s*([ก-๙]+)\s+(?:อำเภอ|เขต|อ\.)\s*([ก-๙]+)',
            cleaned
        )
        if combined_match:
            entities['subdistrict'] = combined_match.group(1).strip()
            entities['district'] = combined_match.group(2).strip()
        else:
            # Individual patterns
            sub_match = re.search(r'(?:ตำบล|แขวง|ต\.)\s*([ก-๙]+)', cleaned)
            if sub_match:
                entities['subdistrict'] = sub_match.group(1).strip()
            
            dist_match = re.search(r'(?:อำเภอ|เขต|อ\.)\s*([ก-๙]+)', cleaned)
            if dist_match:
                entities['district'] = dist_match.group(1).strip()
        
        # Remove province from cleaned
        if entities['province']:
            cleaned = cleaned.replace(entities['province'], '').strip()
        
        # Two-word parsing for remaining words
        structural_words = ['จังหวัด', 'อำเภอ', 'ตำบล', 'แขวง', 'เขต', 'จ.', 'อ.', 'ต.']
        for w in structural_words:
            cleaned = cleaned.replace(w, '')
        
        # ============================================================
        # Filter out agency aliases before assigning to district/subdistrict
        # ============================================================
        agency_alias_set = set(a.lower() for a in AGENCY_ALIASES.keys())
        agency_keywords = ['สังกัด', 'หน่วยงาน', 'ของ', 'ใน', 'ที่มี', 'ที่']
        # Also exclude national-level and modifier keywords that should not be treated as locations
        national_keywords = [
            'ประเทศไทย', 'ประเทศ', 'ทั่วประเทศ', 'ทั้งหมด', 'รวม', 'ไทย',
            'ทุกสังกัด', 'ทุกหน่วยงาน', 'ทุกอำเภอ', 'ทุกจังหวัด', 'ทุกตำบล',
            'สังกัดอื่น', 'สังกัดต่างๆ', 'หน่วยงานอื่น', 'หน่วยงานต่างๆ',
            'สรุป', 'รายละเอียด', 'ข้อมูล', 'ขอ', 'ดู', 'แสดง'
        ]
        exclusion_set = agency_alias_set.union(set(agency_keywords)).union(set(national_keywords))
        
        # Enhanced word filtering - check if any exclusion keyword is contained in the word
        def should_exclude_word(word: str) -> bool:
            word_lower = word.lower()
            # Check if any keyword is contained in the word (for compound words like "ขอทุกสังกัด")
            exclude_keywords = ['สังกัด', 'หน่วยงาน', 'ทั้งหมด', 'ทั้งนั้น', 'ทุก', 'รวม', 'สรุป', 'ขอ', 'ดู', 'แสดง']
            if any(kw in word_lower for kw in exclude_keywords):
                return True
            return word_lower in exclusion_set
        
        words = [w.strip() for w in cleaned.split() 
                 if len(w.strip()) >= 2 
                 and re.match(r'[ก-๙]+', w) 
                 and not should_exclude_word(w.strip())]
        
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
        
        # ============================================================
        # Agency keywords detection
        # ============================================================
        agency_keywords = ['สังกัด', 'หน่วยงาน', 'สพฐ', 'สพฐ.', 'เอกชน', 'อปท', 'อปท.', 
                          'กรมส่งเสริม', 'เทศบาล', 'อบต', 'อบจ',
                          'สำนักงานคณะกรรมการ', 'กรม', 'สช', 'สช.']
        has_agency_kw = any(kw in query_lower for kw in agency_keywords)
        
        has_subdistrict_kw = any(kw in query_lower for kw in ['ตำบล', 'แขวง', 'ต.'])
        has_district_kw = any(kw in query_lower for kw in ['อำเภอ', 'เขต', 'อ.'])
        has_province = entities.get('province') is not None
        
        # ============================================================
        # SMART LEVEL DETECTION:
        # If province is specified WITH agency → use PROVINCE collection (filter by both)
        # If only agency keyword (no province) → use AGENCY collection (ranking)
        # ============================================================
        
        if has_agency_kw:
            # If province is also specified → use PROVINCE with agency filter
            if has_province:
                return QueryLevel.PROVINCE
            # If asking about ranking of agencies → use AGENCY collection
            return QueryLevel.AGENCY
        
        if has_subdistrict_kw or entities.get('subdistrict'):
            return QueryLevel.SUBDISTRICT
        if has_district_kw or entities.get('district'):
            return QueryLevel.DISTRICT
        
        return QueryLevel.PROVINCE
    
    def parse(self, query: str) -> ParsedQuery:
        """Parse query into structured format"""
        entities = self.extract_entities(query)
        
        # ============================================================
        # TRY LLM CLASSIFICATION FIRST (INTELLIGENT)
        # ============================================================
        llm_result = self.llm_classifier.classify(query)
        
        if llm_result:
            # Map LLM intent string to QueryIntent enum
            intent_mapping = {
                'SCHOOL_COUNT': QueryIntent.SCHOOL_COUNT,
                'SCHOOL_LIST': QueryIntent.SCHOOL_LIST,
                'SCHOOL_DETAIL': QueryIntent.SCHOOL_DETAIL,
                'SCHOOL_SEARCH': QueryIntent.SCHOOL_SEARCH,
                'RANKING_MOST': QueryIntent.RANKING_MOST,
                'RANKING_LEAST': QueryIntent.RANKING_LEAST,
                'LOAD_MORE': QueryIntent.LOAD_MORE,
                'GENERAL': QueryIntent.UNKNOWN,
            }
            
            llm_intent = llm_result.get('intent', 'GENERAL')
            intent = intent_mapping.get(llm_intent, QueryIntent.UNKNOWN)
            
            # Use LLM-extracted entities if available
            region = llm_result.get('region') or entities.get('region')
            province = llm_result.get('province') or entities.get('province')
            district = llm_result.get('district') or entities.get('district')
            agency = llm_result.get('agency') or entities.get('agency')
            school_name = llm_result.get('school_name')
            
            level = self.detect_level(query, entities)
            
            return ParsedQuery(
                intent=intent,
                level=level,
                province=province,
                district=district,
                subdistrict=entities.get('subdistrict'),
                agency=agency,
                region=region,
                original_query=query,
                normalized_query=self.normalize_query(query),
                confidence=0.95,  # High confidence for LLM
                school_name=school_name  # Store extracted school name
            )
        
        # ============================================================
        # FALLBACK TO KEYWORD MATCHING
        # ============================================================
        logger.info("⚡ Fallback to keyword matching")
        intent = self.detect_intent(query)
        level = self.detect_level(query, entities)
        
        return ParsedQuery(
            intent=intent,
            level=level,
            province=entities.get('province'),
            district=entities.get('district'),
            subdistrict=entities.get('subdistrict'),
            agency=entities.get('agency'),
            region=entities.get('region'),
            original_query=query,
            normalized_query=self.normalize_query(query),
            confidence=0.8 if entities.get('province') or entities.get('district') else 0.5
        )


# =====================================================================
# DATABASE SEARCH ENGINE
# =====================================================================
class SearchEngine:
    """Production-ready search engine with fallback strategies"""
    
    def __init__(self, client: QdrantClient):
        self.client = client
        self.parser = SmartQueryParser()
    
    def search(self, parsed_query: ParsedQuery, collection_name: str, top_k: int = 50) -> List:
        """
        Smart Search (World Class RAG):
        1. Contextual Filters (Metadata)
        2. Query Expansion (Gemini)
        3. Filtered Vector Search (Hybrid)
        """
        start_time = time.time()
        results = []
        
        try:
            # 1. Build Metadata Filters (Hard Constraints)
            conditions = []
            if parsed_query.province:
                conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=parsed_query.province)))
            if parsed_query.district:
                conditions.append(FieldCondition(key="metadata.district", match=MatchValue(value=parsed_query.district)))
            if parsed_query.subdistrict:
                conditions.append(FieldCondition(key="metadata.subdistrict", match=MatchValue(value=parsed_query.subdistrict)))
            if parsed_query.agency:
                conditions.append(FieldCondition(key="metadata.agency", match=MatchValue(value=parsed_query.agency)))
            
            qdrant_filter = Filter(must=conditions) if conditions else None
            
            # 2. Query Expansion (Make it smarter)
            # Use 'original_query' but optionally remove location words to focus vector search on 'topic'
            # But query embedding usually handles full sentence well.
            # Let's expand/clarify intent.
            expanded_query = self._expand_query(parsed_query.original_query)
            
            # 3. Hybrid Search (Vector + Filter)
            results = self._semantic_search(expanded_query, collection_name, top_k, qdrant_filter)
            logger.info(f"🧠 Smart Search: '{expanded_query}' + Filters={len(conditions)} -> {len(results)} hits")
            
            # 4. Fallback: If Hybrid fail (maybe query is too weird), try exact filter match OR full scroll
            if not results:
                logger.info("⚠️ Vector search failed, falling back to pure metadata filter")
                response = self.client.scroll(
                    collection_name=collection_name,
                    scroll_filter=qdrant_filter, # May be None for full data scan
                    limit=top_k,
                    with_payload=True
                )
                results = response[0]

        except Exception as e:
            logger.error(f"Search error: {e}")
        
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"Search completed in {elapsed:.2f}ms")
        return results

    def _expand_query(self, query: str) -> str:
        """Expand query using Gemini to improve recall"""
        try:
            # Simple expansion: if query is very short, keep it.
            if len(query) < 5: 
                return query
                
            # Use lightweight model for speed
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = f"แปลงคำค้นหานี้ให้เป็นประโยคที่ใช้ค้นหาใน Vector Database ภาษาไทย: '{query}' (ขอแค่ประโยคผลลัพธ์ ไม่ต้องอธิบาย)"
            
            # Set timeout to avoid latency bottleneck
            response = model.generate_content(prompt, generation_config={"max_output_tokens": 50})
            expanded = response.text.strip()
            
            # Sanity check: don't use if too long nonsense
            if len(expanded) > 200:
                return query
                
            return expanded
        except Exception as e:
            logger.warning(f"Query expansion failed: {e}")
            return query
    
    def _exact_match(self, query: ParsedQuery, collection_name: str, top_k: int) -> List:
        """Legacy: Kept for reference or specific use cases"""
        # ... logic moved to main search ...
        return []

    def _fuzzy_match(self, query: ParsedQuery, collection_name: str, top_k: int) -> List:
         """Legacy: Kept for reference"""
         return []
    
    def _semantic_search(self, query: str, collection_name: str, top_k: int, filters: Filter = None) -> List:
        """Semantic search using embeddings with filters"""
        try:
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=query,
                task_type="retrieval_query"
            )
            query_vector = result['embedding']
            
            results = self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                query_filter=filters,
                limit=top_k,
                with_payload=True
            )
            return results
            
        except Exception as e:
            logger.error(f"Semantic search error: {e}")
            return []
    
    def ranking_search(self, parsed_query: ParsedQuery, collection_name: str, top_k: int = 1000) -> List:
        """
        Special search for ranking queries - fetches ALL data or filtered by region/province
        Then aggregates and sorts by total count
        """
        logger.info(f"🏆 Ranking search: region={parsed_query.region}, province={parsed_query.province}")
        
        conditions = []
        
        # Filter by province if specified
        if parsed_query.province:
            conditions.append(
                FieldCondition(key="metadata.province", match=MatchValue(value=parsed_query.province))
            )
            logger.info(f"   Filter by province: {parsed_query.province}")

        # Filter by agency if specified
        if parsed_query.agency:
            conditions.append(
                FieldCondition(key="metadata.agency", match=MatchValue(value=parsed_query.agency))
            )
            logger.info(f"   Filter by agency: {parsed_query.agency}")
        
        # Filter by region if specified
        elif parsed_query.region:
            region_provinces = REGIONS.get(parsed_query.region, [])
            if region_provinces:
                logger.info(f"   Filter by region: {parsed_query.region} ({len(region_provinces)} provinces)")
                # For region, we need to fetch all and filter client-side
                # because Qdrant doesn't support IN operator in basic mode
        
        try:
            if conditions:
                response = self.client.scroll(
                    collection_name=collection_name,
                    scroll_filter=Filter(must=conditions),
                    limit=top_k,
                    with_payload=True
                )
            else:
                response = self.client.scroll(
                    collection_name=collection_name,
                    limit=top_k,
                    with_payload=True
                )
            
            results = response[0]
            
            # Filter by region (client-side)
            if parsed_query.region and not parsed_query.province:
                region_provinces = REGIONS.get(parsed_query.region, [])
                if region_provinces:
                    filtered = []
                    for r in results:
                        meta = r.payload.get('metadata', {})
                        if meta.get('province') in region_provinces:
                            filtered.append(r)
                    results = filtered
                    logger.info(f"   After region filter: {len(results)} results")
            
            logger.info(f"   Ranking search found: {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Ranking search error: {e}")
            return []


# =====================================================================
# RESULT AGGREGATOR
# =====================================================================
class ResultAggregator:
    """Aggregate and format search results"""
    
    def aggregate(self, results: List, level: QueryLevel, is_least: bool = False) -> SearchResult:
        """Aggregate results by location (Province/District/Subdistrict/Agency)"""
        aggregated = defaultdict(lambda: {'agencies': defaultdict(int), 'total': 0})
        
        for hit in results:
            meta = hit.payload.get('metadata', {})
            count = meta.get('count', 0)
            if not count: continue
            
            # Determine grouping key based on level
            name = ""
            if level == QueryLevel.PROVINCE:
                name = meta.get('province', '')
            elif level == QueryLevel.DISTRICT:
                prov = meta.get('province', '')
                dist = meta.get('district', '')
                name = f"{prov}|{dist}" if prov and dist else ""
            elif level == QueryLevel.SUBDISTRICT:
                prov = meta.get('province', '')
                dist = meta.get('district', '')
                sub = meta.get('subdistrict', '')
                name = f"{prov}|{dist}|{sub}" if all([prov, dist, sub]) else ""
            elif level == QueryLevel.AGENCY:
                name = meta.get('agency', '')
            
            if not name: continue
            
            aggregated[name]['total'] += count
            if meta.get('agency'):
                aggregated[name]['agencies'][meta.get('agency')] += count
        
        # Sort and return
        sorted_data = sorted(aggregated.items(), key=lambda x: x[1]['total'], reverse=not is_least)
        return SearchResult(data=sorted_data, count=len(sorted_data), is_least=is_least)

    def aggregate_by_region(self, results: List, is_least: bool = False) -> SearchResult:
        """Aggregate results by region using the REGIONS mapping"""
        # 1. Aggregate by province first
        province_totals = defaultdict(int)
        for hit in results:
            meta = hit.payload.get('metadata', {})
            count = meta.get('count', 0)
            province = meta.get('province')
            if province and count:
                province_totals[province] += count
        
        # 2. Group provinces into regions
        region_aggregated = defaultdict(lambda: {'total': 0})
        for region, provinces in REGIONS.items():
            if region == 'ภาคอีสาน': continue # Alias
            for prov in provinces:
                if prov in province_totals:
                    region_aggregated[region]['total'] += province_totals[prov]
        
        sorted_data = sorted(region_aggregated.items(), key=lambda x: x[1]['total'], reverse=not is_least)
        return SearchResult(data=sorted_data, count=len(sorted_data), is_least=is_least)

    def aggregate_by_agency(self, results: List, province: str = None, region: str = None, is_least: bool = False) -> SearchResult:
        """Aggregate results by agency for a specific province or region"""
        agency_counts = defaultdict(lambda: {'total': 0})
        
        # Get list of provinces if filtering by region
        region_provinces = []
        if region and region != "each_region":
            region_provinces = REGIONS.get(region, [])
        
        for hit in results:
            meta = hit.payload.get('metadata', {})
            agency = meta.get('agency')
            count = meta.get('count', 0)
            hit_province = meta.get('province')
            
            # Filter by province if specified
            if province and hit_province != province:
                continue
            # Filter by region if specified
            if region_provinces and hit_province not in region_provinces:
                continue
                
            if agency and count:
                agency_counts[agency]['total'] += count
        
        sorted_data = sorted(agency_counts.items(), key=lambda x: x[1]['total'], reverse=not is_least)
        return SearchResult(data=sorted_data, count=len(sorted_data), is_least=is_least)

# =====================================================================
# SCHOOL SEARCH ENGINE
# =====================================================================
class SchoolSearchEngine:
    """Search engine for education_schools collection"""
    
    def __init__(self, client: QdrantClient):
        self.client = client
        self.collection = COLLECTIONS["schools"]
    
    def search_by_name(self, name: str, limit: int = 10) -> List:
        """Search schools by name - try text match first, then semantic search (deduplicated by school_code)"""
        results = []
        
        def deduplicate(items, target_limit):
            """Helper to deduplicate by school_code"""
            seen_codes = set()
            unique = []
            for item in items:
                code = item.payload.get('metadata', {}).get('school_code') if hasattr(item, 'payload') else None
                if code and code not in seen_codes:
                    seen_codes.add(code)
                    unique.append(item)
                    if len(unique) >= target_limit:
                        break
            return unique
        
        # 1. Try text-match filter first (more accurate for exact names)
        try:
            response = self.client.scroll(
                collection_name=self.collection,
                scroll_filter=Filter(must=[
                    FieldCondition(key="metadata.school_name", match=MatchValue(value=name))
                ]),
                limit=limit * 5,  # Overfetch for deduplication
                with_payload=True
            )
            results = deduplicate(response[0], limit)
            if results:
                logger.info(f"🏫 Text match found {len(results)} unique schools for '{name}'")
                return results
        except Exception as e:
            logger.warning(f"Text match failed: {e}")
        
        # 2. Fallback to semantic search
        try:
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=f"โรงเรียน{name}",
                task_type="retrieval_query"
            )
            query_vector = result['embedding']
            
            results = self.client.search(
                collection_name=self.collection,
                query_vector=query_vector,
                limit=limit * 5,  # Overfetch for deduplication
                with_payload=True
            )
            unique_results = deduplicate(results, limit)
            logger.info(f"🔍 Semantic search found {len(unique_results)} unique schools for '{name}'")
            return unique_results
        except Exception as e:
            logger.error(f"School search by name error: {e}")
            return []
    
    def find_similar_schools(self, query: str, province: str = None, top_k: int = 5, threshold: float = 0.5) -> List[Tuple[str, float]]:
        """Find school names similar to query using fuzzy matching (for typo tolerance)"""
        try:
            # Fetch all school names from Qdrant (limit to a manageable number)
            conditions = []
            if province:
                conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))
            
            scroll_filter = Filter(must=conditions) if conditions else None
            
            response = self.client.scroll(
                collection_name=self.collection,
                scroll_filter=scroll_filter,
                limit=500,  # Limit for performance
                with_payload=["metadata.school_name", "metadata.province", "metadata.district"]
            )
            
            all_schools = response[0]
            if not all_schools:
                return []
            
            # Calculate similarity scores using SequenceMatcher
            scored_schools = []
            query_lower = query.lower()
            
            for school in all_schools:
                meta = school.payload.get('metadata', {})
                school_name = meta.get('school_name', '')
                if not school_name:
                    continue
                    
                # Calculate similarity ratio
                ratio = SequenceMatcher(None, query_lower, school_name.lower()).ratio()
                
                # Also check if query is a substring (partial match)
                if query_lower in school_name.lower() or school_name.lower() in query_lower:
                    ratio = max(ratio, 0.7)  # Boost substring matches
                
                if ratio >= threshold:
                    scored_schools.append({
                        'name': school_name,
                        'province': meta.get('province', '-'),
                        'district': meta.get('district', '-'),
                        'score': ratio
                    })
            
            # Sort by score descending and return top_k
            scored_schools.sort(key=lambda x: x['score'], reverse=True)
            logger.info(f"🔤 Found {len(scored_schools)} similar schools for '{query}' (threshold={threshold})")
            return scored_schools[:top_k]
            
        except Exception as e:
            logger.error(f"Fuzzy school search error: {e}")
            return []
    
    def search_by_province(self, province: str, agency: str = None, limit: int = 20) -> List:
        """List schools in a province, optionally filtered by agency (deduplicated by school_code)"""
        conditions = [
            FieldCondition(key="metadata.province", match=MatchValue(value=province))
        ]
        if agency:
            conditions.append(
                FieldCondition(key="metadata.agency", match=MatchValue(value=agency))
            )
        
        try:
            # Fetch more results to account for duplicates
            response = self.client.scroll(
                collection_name=self.collection,
                scroll_filter=Filter(must=conditions),
                limit=limit * 5,  # Overfetch to handle duplicates
                with_payload=True
            )
            
            # Deduplicate by school_code
            seen_codes = set()
            unique_results = []
            for point in response[0]:
                code = point.payload.get('metadata', {}).get('school_code')
                if code and code not in seen_codes:
                    seen_codes.add(code)
                    unique_results.append(point)
                    if len(unique_results) >= limit:
                        break
            
            return unique_results
        except Exception as e:
            logger.error(f"School search by province error: {e}")
            return []
    
    def search_by_district(self, province: str, district: str, agency: str = None, limit: int = 20) -> List:
        """List schools in a district with robust name matching (deduplicated by school_code)"""
        
        # 1. Normalize district name (remove prefixes if present)
        base_district = district.replace('อำเภอ', '').replace('อ.', '').strip()
        
        # 2. Generate standard variations
        district_variants = {
            base_district,                          # "เมือง", "เบตง"
            f"{base_district}{province}",           # "เมืองยะลา", "เบตงยะลา"
            f"อำเภอ{base_district}",                # "อำเภอเมือง", "อำเภอเบตง"
            f"อำเภอ{base_district}{province}",      # "อำเภอเมืองยะลา"
            f"อ.{base_district}",                   # "อ.เมือง"
            f"อ.{base_district}{province}"          # "อ.เมืองยะลา"
        }
            
        logger.info(f"🔎 Searching district variations for '{district}': {list(district_variants)}")

        # Construct filter with OR condition for district
        district_should = [
            FieldCondition(key="metadata.district", match=MatchValue(value=d))
            for d in district_variants
        ]
        
        conditions = [
            FieldCondition(key="metadata.province", match=MatchValue(value=province)),
            Filter(should=district_should) # Matches ANY of the district variants
        ]
        
        if agency:
            conditions.insert(0, FieldCondition(key="metadata.agency", match=MatchValue(value=agency)))
        
        try:
            # Overfetch to handle duplicates
            response = self.client.scroll(
                collection_name=self.collection,
                scroll_filter=Filter(must=conditions),
                limit=limit * 5,
                with_payload=True
            )
            
            # Deduplicate by school_code
            seen_codes = set()
            unique_results = []
            for point in response[0]:
                code = point.payload.get('metadata', {}).get('school_code')
                if code and code not in seen_codes:
                    seen_codes.add(code)
                    unique_results.append(point)
                    if len(unique_results) >= limit:
                        break
            
            return unique_results
        except Exception as e:
            logger.error(f"School search by district error: {e}")
            return []
    
    def get_school_details(self, school_name: str) -> Optional[Dict]:
        """Get detailed information about a specific school"""
        # Preprocessing: remove 'โรงเรียน' prefix if present
        clean_name = school_name.strip()
        for prefix in ['โรงเรียน', 'ร.ร.', 'รร.', 'รร']:
            if clean_name.startswith(prefix):
                clean_name = clean_name[len(prefix):].strip()
        
        logger.info(f"🔍 Searching for school: '{school_name}' → '{clean_name}'")
        
        # Use semantic search to find the school
        results = self.search_by_name(clean_name, limit=10)
        if results:
            # Try to find best match by checking if school name contains the query
            for res in results:
                meta = res.payload.get('metadata', {})
                db_school_name = meta.get('school_name', '').lower()
                query_name = school_name.lower()
                # Check if query matches the school name
                if query_name in db_school_name or db_school_name in query_name:
                    logger.info(f"🏫 Found school: {meta.get('school_name')}")
                    return meta
            # If no exact match, return top result with high score
            top_result = results[0]
            if hasattr(top_result, 'score') and top_result.score > 0.7:
                logger.info(f"🏫 Best match: {results[0].payload.get('metadata', {}).get('school_name')} (score: {top_result.score})")
                return results[0].payload.get('metadata', {})
        return None
    
    def count_schools(self, province: str = None, district: str = None, agency: str = None) -> int:
        """Count unique schools with optional filters (deduplicated by school_code)"""
        conditions = []
        if province:
            conditions.append(
                FieldCondition(key="metadata.province", match=MatchValue(value=province))
            )
        if district:
            conditions.append(
                FieldCondition(key="metadata.district", match=MatchValue(value=district))
            )
        if agency:
            conditions.append(
                FieldCondition(key="metadata.agency", match=MatchValue(value=agency))
            )
        
        try:
            # Scroll through all results and deduplicate by school_code
            scroll_filter = Filter(must=conditions) if conditions else None
            unique_codes = set()
            offset = None
            
            while True:
                response = self.client.scroll(
                    collection_name=self.collection,
                    scroll_filter=scroll_filter,
                    limit=1000,
                    offset=offset,
                    with_payload=["metadata.school_code"]
                )
                points, next_offset = response
                
                if not points:
                    break
                    
                for point in points:
                    code = point.payload.get('metadata', {}).get('school_code')
                    if code:
                        unique_codes.add(code)
                
                if next_offset is None:
                    break
                offset = next_offset
            
            logger.info(f"🏫 Unique schools count: {len(unique_codes)}")
            return len(unique_codes)
        except Exception as e:
            logger.error(f"School count error: {e}")
            return 0


# =====================================================================
# RESPONSE FORMATTER
# =====================================================================
class ResponseFormatter:
    """Format responses for different query types"""
    
    def __init__(self, model: Optional[genai.GenerativeModel] = None, model_name: str = 'models/gemini-1.5-flash'):
        self.model = model
        self.model_name = model_name
        self.level_names = {
            QueryLevel.PROVINCE: "จังหวัด",
            QueryLevel.DISTRICT: "อำเภอ/เขต",
            QueryLevel.SUBDISTRICT: "ตำบล/แขวง",
            QueryLevel.AGENCY: "สังกัด"
        }
    
    @staticmethod
    def format_location(name: str, level: QueryLevel) -> str:
        """Format location name"""
        # Safety: If name has no separator, just return it as-is (e.g., region names)
        if '|' not in name:
            return name
        
        if level == QueryLevel.PROVINCE:
            return f"จังหวัด{name}"
        elif level == QueryLevel.DISTRICT:
            parts = name.split('|')
            if len(parts) < 2:
                return name
            is_bangkok = 'กรุงเทพ' in parts[0]
            term = "เขต" if is_bangkok else "อำเภอ"
            return f"{term}{parts[1]} ({parts[0]})"
        elif level == QueryLevel.SUBDISTRICT:
            parts = name.split('|')
            if len(parts) < 3:
                return name
            is_bangkok = 'กรุงเทพ' in parts[0]
            sub_term = "แขวง" if is_bangkok else "ตำบล"
            return f"{sub_term}{parts[2]} ({parts[1]}, {parts[0]})"
        elif level == QueryLevel.AGENCY:
            return name
        return name
    
    def format(self, result: SearchResult, parsed_query: ParsedQuery) -> Generator[str, None, None]:
        """Format search results into response (Persona: Nong Dio Hybrid)"""
        
        # 1. NO DATA FOUND -> Fallback to General Knowledge (LLM)
        if not result.data:
            if self.model: 
                yield from self._generate_general_knowledge_response(parsed_query)
                return
            else:
                yield "😔 **น้องดีโอหาข้อมูลในระบบไม่เจอครับ**\n\n"
                return
        
        intent = parsed_query.intent
        level = parsed_query.level
        
        # 2. Add AI Insight (Optional - skip if fails/quota)
        # If we have a model, try to stream a friendly explanation FIRST
        ai_insight_text = ""
        if self.model:
            try:
                for chunk in self._generate_ai_insight(result, parsed_query):
                    ai_insight_text += chunk
                    yield chunk
                if ai_insight_text:
                    yield "\n\n---\n\n" # Visual separator for the structured data
            except Exception as e:
                logger.warning(f"AI Insight skipped (silently): {e}")
                # Still continue to structured data! No error shown to user.
        
        # 3. Structured Response (Data & Charts) - ALWAYS runs even if AI fails
        if intent in [QueryIntent.RANKING_MOST, QueryIntent.RANKING_LEAST]:
            yield from self._format_ranking(result, level, parsed_query)
        elif len(result.data) == 1:
            yield from self._format_single(result, level, parsed_query)
        else:
            yield from self._format_listing(result, level, parsed_query)

    def _generate_ai_insight(self, result: SearchResult, parsed_query: ParsedQuery) -> Generator[str, None, None]:
        """Generate a short AI insight/explanation of the data"""
        try:
            # Prepare summary for AI
            summary_items = []
            for name, data in result.data[:10]:
                summary_items.append(f"{name} ({data['total']} แห่ง)")
            
            prompt = f"""
role: คุณคือ "น้องดีโอ" (DO-MOE) ผู้ช่วยอัจฉริยะที่เชี่ยวชาญสถิติการศึกษาและมีหัวใจบริการ
style: พูดจาฉะฉาน เป็นกันเอง (ครับ/ผม) สุภาพแต่อบอุ่น แฝงความรอบรู้ + Emoji ✨
task: วิเคราะห์ข้อมูลสถิติที่น้องดีโอหามาให้พี่ๆ ได้อย่าง "ลึกซึ้ง" และ "เป็นธรรมชาติ"
      - ห้ามพูดเหมือนหุ่นยนต์ หรือสรุปแค่ตัวเลข
      - ให้วิเคราะห์ภาพรวม เช่น "จะเห็นได้ว่าในพื้นที่นี้มีสัดส่วนของโรงเรียนเอกชนเยอะกว่าปกติ ซึ่งสะท้อนถึง..."
      - เปรียบเทียบจุดที่น่าสนใจหรือสังเกตเห็นจากข้อมูล (เช่น สังกัดไหนเยอะสุด เพราะอะไร หรือมีข้อเสนอแนะเบื้องต้น)
      - ตอบให้เหมือนผู้เชี่ยวชาญกำลังบรรยายให้คนในครอบครัวฟัง
      - ความยาว 3-4 ประโยคที่ดูมีคุณค่าและเป็นมืออาชีพ

data overview: {', '.join(summary_items)}
query context: {parsed_query.original_query}

answer (Nong Dio style):
"""
            response = self.model.generate_content(prompt, stream=True)
            for chunk in response:
                yield chunk.text
        except Exception as e:
            logger.error(f"AI Insight error: {e}")
            return

    def _generate_general_knowledge_response(self, parsed_query: ParsedQuery) -> Generator[str, None, None]:
        """Generate response using LLM General Knowledge (When DB has no data)"""
        # yield "🤖 **น้องดีโอขอตอบจากความรู้รอบตัวนะครับ!**\n\n" # Optional disclaimer? User said "Don't say no info".
        # Let's make it seamless. Just answer.
        # Maybe a tiny hint? "จากการประมวลผล..." (Processing...)
        
        try:
            prompt = f"""
role: คุณคือ "น้องดีโอ" (DO-MOE AI)
style: น่ารัก เป็นกันเอง สุภาพ (ครับ/ผม) + Emoji 🌟
situation: ไม่พบข้อมูลในฐานข้อมูลเฉพาะทาง (Database) เลยต้องตอบด้วยความรู้ทั่วไป (General Knowledge)
task: ตอบคำถามนี้โดยใช้ความรู้ของคุณเองให้อย่างเต็มที่ที่สุด

question: {parsed_query.original_query}

instruction:
1. ตอบให้เหมือนผู้เชี่ยวชาญการศึกษา
2. ห้ามบอกว่า "ไม่พบข้อมูล" หรือ "ไม่มีข้อมูล"
3. ตอบให้เป็นธรรมชาติ เหมือนเราคุยกับคนรู้ใจ
4. ถ้าคำถามเฉพาะเจาะจงกับข้อมูลภายในมากเกินไป (เช่น ถามจำนวนนักเรียน รร.บ้านหนองงูเห่า) ให้ตอบกลางๆ หรือคาดการณ์อย่างมีหลักการ หรืออธิบายบริบทที่เกี่ยวข้องแทน

answer:
"""
            response = self.model.generate_content(prompt, stream=True)
            for chunk in response:
                yield chunk.text
                
        except Exception as e:
            logger.error(f"General Knowledge Error: {e}")
            # Try once with fallback model if quota exceeded
            if "quota" in str(e).lower() and self.model_name != 'models/gemini-1.5-flash-latest':
                try:
                    fallback_model = genai.GenerativeModel('models/gemini-1.5-flash-latest')
                    response = fallback_model.generate_content(prompt, stream=True)
                    for chunk in response:
                        yield chunk.text
                    return
                except:
                    pass
            yield "😅 ขอโทษครับ น้องดีโอประมวลผลไม่ไหว (ติดโควตา Gemini) รบกวนพี่ลองถามใหม่ถัดไปนะครับ หรือลองถามข้อมูลรายจังหวัดดูแทนนะครับ"

    def _generate_rag_response(self, result: SearchResult, parsed_query: ParsedQuery) -> Generator[str, None, None]:
        """Generate friendly answer using Gemini (RAG)"""
        yield "🤖 **น้องดีโอจัดให้!** (กำลังสรุปข้อมูลให้อยู่นะครับ...)\n\n"
        
        try:
            # Construct Context
            context_text = ""
            for i, (name, data) in enumerate(result.data[:15]): # Limit context
                 meta = data.get('metadata', {})
                 details = str(data) # specific fields better but this is generic fallback
                 context_text += f"Record {i+1}: {name} | Info: {details}\n"
            
            prompt = f"""
role: คุณคือ "น้องดีโอ" (DO-MOE) AI ผู้ช่วยค้นหาข้อมูลการศึกษา 3 จังหวัดชายแดนใต้
style: น่ารัก ใช้งานง่าย ใช้คำสุภาพ (ครับ/ผม) และมี Emoji 🌟
task: ตอบคำถามจากข้อมูล Context ที่ให้มา (อย่ามั่วข้อมูลเอง)

context:
{context_text}

question: {parsed_query.original_query}

instruction:
1. ตอบคำถามให้ตรงประเด็น สั้นกระชับ
2. ถ้าเป็นการขอรายชื่อ ให้แสดงเป็น Bullet points
3. สรุปใจความสำคัญให้ด้วย
4. ถ้าข้อมูลใน context ไม่ตอบโจทย์ ให้บอกตามตรงและแนะนำให้ค้นใหม่

answer:
"""
            response = self.model.generate_content(prompt, stream=True)
            for chunk in response:
                yield chunk.text
                
        except Exception as e:
            logger.error(f"RAG Error: {e}")
            yield "😓 ขอโทษครับ น้องดีโอประมวลผลไม่ทัน... งั้นดูรายชื่อตามนี้แทนนะครับ:\n\n"
            yield from self._format_listing(result, parsed_query.level, parsed_query)
    
    def _format_chart_data(self, chart_type: str, data_points: List[dict], title: str = "") -> str:
        """Generate chart data block"""
        import json
        payload = {"type": chart_type, "data": data_points, "title": title}
        return f"\n\n<chart>{json.dumps(payload, ensure_ascii=False)}</chart>"

    def _format_ranking(self, result: SearchResult, level: QueryLevel, parsed_query: ParsedQuery) -> Generator[str, None, None]:
        """Format ranking response"""
        is_least = result.is_least
        num_show = min(10, len(result.data))
        
        emoji = "🥇" if not is_least else "📊"
        title = "น้อยที่สุด" if is_least else "มากที่สุด"
        loc_type = self.level_names.get(level, "รายการ")
        
        yield f"### {emoji} ผลการจัดอันดับ{loc_type}ที่มีโรงเรียน{title}ครับ\n\n"
        yield "น้องดีโอสรุปข้อมูลมาให้ตามนี้เลยครับ 👇\n\n"
        
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        
        chart_data = []
        
        for i, (name, data) in enumerate(result.data[:num_show], 1):
            medal = medals.get(i, "")
            # Detect agency ranking within province (source starts with 'province_agencies_')
            if hasattr(result, 'source') and result.source.startswith('province_agencies_'):
                display = name  # Use agency name directly
            else:
                display = self.format_location(name, level)
                
            # Chart Data
            short_name = display  # Use formatted display name
            chart_data.append({"name": short_name, "value": data['total']})
            
            # Format: Top 3 get bold name and medal, others standard
            if i <= 3:
                yield f"{medal} **{i}. {display}** ({data['total']:,} แห่ง)\n"
            else:
                yield f"{i}. {display}: {data['total']:,} แห่ง\n"
        
        total_all = sum(d['total'] for _, d in result.data)
        yield f"\n\n✨ *พบข้อมูลทั้งหมด {len(result.data)} รายการ (รวม {total_all:,} โรงเรียน) ครับ*\n"
        
        # Append Chart
        yield self._format_chart_data("bar", chart_data, f"สถิติ{title}")
    
    def _format_single(self, result: SearchResult, level: QueryLevel, parsed_query: ParsedQuery) -> Generator[str, None, None]:
        """Format single result"""
        name, data = result.data[0]
        # Use agency name if available in source
        if hasattr(result, 'source') and result.source.startswith('province_agencies_'):
             display = name
        else:
             display = self.format_location(name, level)
        
        yield f"### 📊 ข้อมูลจำนวนโรงเรียนใน {display} ครับ\n\n"
        
        if data['agencies']:
            yield "✨ **แยกตามสังกัดดังนี้ครับ:**\n\n"
            
            chart_data = []
            
            for agency, count in sorted(data['agencies'].items(), key=lambda x: x[1], reverse=True):
                yield f"- {agency}: **{count:,}** แห่ง\n"
                chart_data.append({"name": agency, "value": count})
                
            yield f"\n**รวมทั้งหมด:** **{data['total']:,}** แห่ง\n"
            
            # Append Chart
            yield self._format_chart_data("pie", chart_data, f"สัดส่วนสังกัด {display}")
            
        else:
            yield f"**รวมทั้งหมด:** **{data['total']:,}** แห่ง\n"
    
    def _format_listing(self, result: SearchResult, level: QueryLevel, parsed_query: ParsedQuery) -> Generator[str, None, None]:
        """Format listing response"""
        # Removed robotic "Found X items" header
        yield "✨ **ข้อมูลสรุปที่น้องคัดสรรมาให้ครับ:**\n\n"
        
        chart_data = []
        
        for i, (name, data) in enumerate(result.data[:10], 1):
            if hasattr(result, 'source') and result.source.startswith('province_agencies_'):
                display = name
            else:
                display = self.format_location(name, level)
            
            yield f"**{i}. {display}**: {data['total']:,} แห่ง\n"
            
            # Add to chart data
            chart_data.append({"name": display, "value": data['total']})
        
        if len(result.data) > 10:
            yield f"\n*...และอีก {len(result.data) - 10} รายการ*\n"
            
        # Add Bar Chart for Comparison/Listing if > 1 item
        if len(chart_data) > 1:
             yield self._format_chart_data("bar", chart_data, f"เปรียบเทียบจำนวนโรงเรียน")
    
    def _format_summary(self, result: SearchResult, level: QueryLevel, parsed_query: ParsedQuery) -> Generator[str, None, None]:
        """Format summary response"""
        yield f"### 📊 สรุปข้อมูล ({len(result.data)} รายการ)\n\n"
        
        for i, (name, data) in enumerate(result.data[:5], 1):
            display = self.format_location(name, level)
            yield f"**{i}.** {display}: **{data['total']:,}** แห่ง\n"
        
        total_all = sum(d['total'] for _, d in result.data)
        yield f"\n**รวมทั้งหมด:** **{total_all:,}** โรงเรียน\n"


# =====================================================================
# CONVERSATION MEMORY - Enhanced context retention with session support
# =====================================================================
class ConversationMemory:
    """Enhanced memory to retain context from previous questions"""
    
    def __init__(self):
        self.last_province: Optional[str] = None
        self.last_district: Optional[str] = None
        self.last_intent: Optional[QueryIntent] = None
        self.last_level: Optional[QueryLevel] = None
        self.last_agency: Optional[str] = None
        self.last_query: Optional[str] = None
    
    def update(self, parsed: ParsedQuery, original_query: str = None):
        """Update memory with new parsed query"""
        if parsed.province:
            self.last_province = parsed.province
        if parsed.district:
            self.last_district = parsed.district
        if parsed.intent:
            self.last_intent = parsed.intent
        if parsed.level:
            self.last_level = parsed.level
        if parsed.agency:
            self.last_agency = parsed.agency
        if original_query:
            self.last_query = original_query
    
    def extract_from_history(self, history: List[Dict]) -> None:
        """Extract context from chat history"""
        if not history:
            return
        
        # Look at last 4 messages for context
        recent = history[-4:] if len(history) > 4 else history
        
        for msg in recent:
            content = msg.get('content', '') if isinstance(msg, dict) else str(msg)
            content_lower = content.lower()
            
            # Extract province from previous messages
            for province in THAI_PROVINCES:
                if province.lower() in content_lower:
                    self.last_province = province
                    logger.info(f"   📍 Extracted province from history: {province}")
                    break
            
            # Extract agency patterns
            agency_patterns = {
                'สพฐ': 'สพฐ.',
                'สช': 'สช.',
                'เอกชน': 'สช.',
                'อปท': 'อปท.',
                'ท้องถิ่น': 'อปท.',
                'ตชด': 'ตชด.',
                'กทม': 'กทม.',
            }
            for pattern, agency in agency_patterns.items():
                if pattern in content_lower:
                    self.last_agency = agency
                    logger.info(f"   🏛️ Extracted agency from history: {agency}")
                    break
    
    def apply_context(self, parsed: ParsedQuery, query: str) -> ParsedQuery:
        """Apply context from memory to current query if needed"""
        query_lower = query.lower()
        
        # Enhanced follow-up patterns - more comprehensive
        follow_up_patterns = [
            'แล้ว', 'ละ', 'ล่ะ', 'หล่ะ', 'เหมือนกัน', 'เดียวกัน',
            'ขอ', 'ทั้งหมด', 'ทุก', 'อีก', 'ต่อ', 'เพิ่ม', 'อื่น',
            'รวม', 'สรุป', 'ทั้งนั้น', 'หมด', 'บ้าง'
        ]
        
        # Check if this looks like a follow-up question
        is_short_query = len(query) < 50
        has_follow_up_word = any(p in query_lower for p in follow_up_patterns)
        lacks_location = not parsed.province and not parsed.district
        
        # Detect "ทุกสังกัด" or "ทั้งหมด" type queries
        is_all_agencies_query = any(p in query_lower for p in ['ทุกสังกัด', 'ทั้งหมด', 'สังกัดอื่น', 'ทุกหน่วยงาน', 'ทั้งนั้น'])
        
        is_follow_up = is_short_query and (has_follow_up_word or lacks_location)
        
        if is_follow_up and self.last_province:
            logger.info(f"🔄 Follow-up question detected: '{query}'")
            logger.info(f"   Memory: province={self.last_province}, district={self.last_district}, agency={self.last_agency}")
            
            # Apply stored province if current query doesn't have one AND doesn't have a region
            # (Region queries should NOT be narrowed down to a single province from memory)
            if not parsed.province and not parsed.region and self.last_province:
                parsed.province = self.last_province
                logger.info(f"   ✅ Applied province from memory: {self.last_province}")
            elif parsed.region:
                logger.info(f"   ℹ️ Region query detected - skipping province memory")
            
            # Apply stored district if relevant
            if not parsed.district and self.last_district:
                parsed.district = self.last_district
                logger.info(f"   ✅ Applied district from memory: {self.last_district}")
            
            # For "ทุกสังกัด" queries, clear agency filter to get all
            if is_all_agencies_query:
                parsed.agency = None  # Clear to get all agencies
                parsed.level = QueryLevel.PROVINCE  # Query at province level for breakdown
                parsed.intent = QueryIntent.COUNT  # Force COUNT intent for proper aggregation
                logger.info(f"   ✅ All-agencies query: cleared agency filter, level=province, intent=count")
            
            # Keep the same intent/level if current one is generic
            if self.last_intent and parsed.intent == QueryIntent.COUNT:
                parsed.intent = self.last_intent
                logger.info(f"   ✅ Applied intent: {self.last_intent.value}")
        
        return parsed
    
    def clear(self):
        """Clear all memory"""
        self.last_province = None
        self.last_district = None
        self.last_intent = None
        self.last_level = None
        self.last_agency = None
        self.last_query = None
    
    def __repr__(self):
        return f"Memory(province={self.last_province}, district={self.last_district}, agency={self.last_agency})"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize memory to dictionary"""
        return {
            'last_province': self.last_province,
            'last_district': self.last_district,
            'last_intent': self.last_intent.value if self.last_intent else None,
            'last_level': self.last_level.value if self.last_level else None,
            'last_agency': self.last_agency,
            'last_query': self.last_query
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationMemory':
        """Deserialize memory from dictionary"""
        mem = cls()
        mem.last_province = data.get('last_province')
        mem.last_district = data.get('last_district')
        mem.last_agency = data.get('last_agency')
        mem.last_query = data.get('last_query')
        
        if data.get('last_intent'):
            try: mem.last_intent = QueryIntent(data['last_intent'])
            except: pass
            
        if data.get('last_level'):
            try: mem.last_level = QueryLevel(data['last_level'])
            except: pass
            
        return mem


# Session-based memory storage (for Flask API multi-user support)
session_memories: Dict[str, ConversationMemory] = {}


class SemanticCache:
    """Semantic Caching using Qdrant for instant replies"""
    
    def __init__(self, client: QdrantClient, collection_name: str = "semantic_cache"):
        self.client = client
        self.collection_name = collection_name
        self.vector_size = 768 # models/text-embedding-004
        self.threshold = 0.97
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Create collection if not exists"""
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            if not exists:
                logger.info(f"🆕 Creating semantic cache collection: {self.collection_name}")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE)
                )
        except Exception as e:
            logger.error(f"Error initializing semantic cache: {e}")

    def check(self, query: str) -> Optional[str]:
        """Check cache for similar queries"""
        try:
            # Generate embedding for the query
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=query,
                task_type="retrieval_query"
            )
            vector = result['embedding']
            
            # Search in cache
            hits = self.client.search(
                collection_name=self.collection_name,
                query_vector=vector,
                limit=1
            )
            
            if hits and hits[0].score >= self.threshold:
                logger.info(f"⚡ Cache Hit! Score: {hits[0].score:.4f}")
                return hits[0].payload.get("response")
                
        except Exception as e:
            logger.warning(f"Cache check failed: {e}")
        return None

    def save(self, query: str, response: str):
        """Save response to cache"""
        try:
            import uuid
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=query,
                task_type="retrieval_query"
            )
            vector = result['embedding']
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    PointStruct(
                        id=str(uuid.uuid4()),
                        vector=vector,
                        payload={"query": query, "response": response, "timestamp": time.time()}
                    )
                ]
            )
        except Exception as e:
            logger.warning(f"Cache save failed: {e}")


# =====================================================================
# HYBRID CACHE (Redis L1 + Semantic L2)
# =====================================================================
class HybridCache:
    """
    Two-layer cache for production:
    - L1: Redis (fast exact match, ~1ms)
    - L2: SemanticCache (similar query match, ~500ms)
    """
    
    def __init__(self, qdrant_client: QdrantClient):
        self.semantic_cache = SemanticCache(qdrant_client)
        self.redis_client = None
        self.ttl = int(os.getenv('REDIS_CACHE_TTL', 3600))  # 1 hour default
        
        # Try to connect to Redis
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis connection with graceful fallback"""
        try:
            import redis
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            # Test connection
            self.redis_client.ping()
            logger.info(f"✅ Redis connected: {redis_url}")
        except Exception as e:
            logger.warning(f"⚠️ Redis unavailable, using Semantic cache only: {e}")
            self.redis_client = None
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query for consistent hashing"""
        return query.lower().strip()
    
    def _get_cache_key(self, query: str) -> str:
        """Generate Redis key from query"""
        normalized = self._normalize_query(query)
        import hashlib
        hash_val = hashlib.md5(normalized.encode()).hexdigest()[:16]
        return f"domoe:cache:{hash_val}"
    
    def check(self, query: str) -> Optional[str]:
        """Check cache: Redis first, then Semantic"""
        # L1: Try Redis (fast exact match)
        if self.redis_client:
            try:
                cache_key = self._get_cache_key(query)
                cached = self.redis_client.get(cache_key)
                if cached:
                    logger.info(f"⚡ Redis Cache Hit!")
                    return cached
            except Exception as e:
                logger.warning(f"Redis check failed: {e}")
        
        # L2: Fall back to Semantic Cache
        return self.semantic_cache.check(query)
    
    def save(self, query: str, response: str):
        """Save to both caches"""
        # L1: Save to Redis
        if self.redis_client:
            try:
                cache_key = self._get_cache_key(query)
                self.redis_client.setex(cache_key, self.ttl, response)
                logger.info(f"💾 Saved to Redis (TTL={self.ttl}s)")
            except Exception as e:
                logger.warning(f"Redis save failed: {e}")
        
        # L2: Save to Semantic Cache
        self.semantic_cache.save(query, response)


# =====================================================================
# MAIN CHATBOT CLASS
# =====================================================================
class EducationChatbot:
    """Production-ready Education Chatbot"""
    
    def __init__(self, model_name: str = 'gemini-2.0-flash-exp'):
        logger.info("🚀 Initializing Education Chatbot v5.0...")
        
        self.parser = SmartQueryParser()
        self.search_engine = SearchEngine(qdrant_client)
        self.aggregator = ResultAggregator()
        self.memory = ConversationMemory()  # Simple memory for follow-up questions
        self.cache = HybridCache(qdrant_client) # ✨ Redis L1 + Semantic L2 Cache
        self.model = self._init_model(model_name)
        self.formatter = ResponseFormatter(model=self.model, model_name=model_name) # ✨ Pass model to enable AI Insights
        self.collections = self._get_collections()
        
        logger.info(f"✅ Chatbot ready with {len(self.collections)} collections")
    
    def _init_model(self, model_name: str):
        """Initialize LLM with Groq → Gemini fallback"""
        try:
            # Use MultiProviderLLM for automatic fallback
            llm = MultiProviderLLM(gemini_model=model_name)
            self.model_name = f"Groq:{GROQ_MODEL} → Gemini:{model_name}" if GROQ_API_KEY else f"Gemini:{model_name}"
            logger.info(f"✅ Using model: {self.model_name}")
            return llm
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            return None
    
    def _get_collections(self) -> Dict[str, str]:
        """Get available collections"""
        available = {}
        try:
            all_collections = qdrant_client.get_collections()
            for level, name in COLLECTIONS.items():
                if any(c.name == name for c in all_collections.collections):
                    available[level] = name
                    logger.info(f"   ✅ {level}: {name}")
        except Exception as e:
            logger.error(f"Failed to get collections: {e}")
        return available
    
    def chat(self, message: str, history: List = None) -> Generator[Tuple[List, str], None, None]:
        """Main chat function with streaming"""
        if not message.strip():
            yield history or [], ""
    def _classify_intent_with_llm(self, query: str) -> str:
        """Use LLM to classify query intent: 'GENERAL' or 'EDUCATION'"""
        try:
            # Quick check for very short queries
            if len(query) < 4:
                return "GENERAL"
                
            prompt = f"""
            Classify this query into one category:
            1. GENERAL: Greetings, small talk, asking "who are you", "what can you do", "eating?", "where are you going?", jokes, weather, generic questions NOT related to education.
            2. EDUCATION: Questions about schools, students, teachers, stats, locations, rankings, comparisons, finding schools, educational data.
            
            Query: "{query}"
            
            Return ONLY the word "GENERAL" or "EDUCATION".
            """
            # Use faster model for classification if available? No, self.model is fine.
            response = self.model.generate_content(prompt)
            return response.text.strip().upper()
        except Exception as e:
            logger.error(f"LLM Classification failed: {e}")
            return "EDUCATION" # Default to Education to be safe

    def _rag_fallback(self, query: str) -> str:
        """Universal Fallback: Use RAG to answer unstructured queries"""
        try:
            # 🚨 FIRST: Check if this is a non-education query → Suggest category switch
            intent_type = self._classify_intent_with_llm(query)
            current_category = getattr(self, '_current_category', 'general')
            
            if "GENERAL" in intent_type and current_category in ['school', 'student']:
                category_name = 'โรงเรียน' if current_category == 'school' else 'นักเรียน'
                return (
                    f"😊 สวัสดีครับ! น้องดีโอเห็นว่าคำถาม \"{query}\" ดูเหมือนจะเป็นเรื่องทั่วไปนะครับ\n\n"
                    f"ขณะนี้คุณอยู่ในโหมด **{category_name}** ซึ่งเน้นข้อมูลการศึกษาโดยเฉพาะครับ\n\n"
                    f"💡 **แนะนำ:** กรุณาสลับไปยังหมวด **\"ทั่วไป\"** ในแถบด้านซ้าย "
                    f"เพื่อให้น้องดีโอช่วยเหลือได้เต็มที่ครับ! ✨"
                )
            
            # 1. Retrieve Context from Schools and Stats
            msg = f"🧠 RAG Fallback: Searching context for '{query}'..."
            logger.info(msg)
            
            context_items = []
            
            # A. Search Schools (Top 3)
            schools = self.search_engine._semantic_search(query, self.collections['schools'], top_k=3)
            for s in schools:
                m = s.payload.get('metadata', {})
                context_items.append(f"School: {m.get('school_name')} (จ.{m.get('province')}) - สังกัด: {m.get('agency')}")
                
            # B. Search Province Stats (Top 3)
            stats = self.search_engine._semantic_search(query, self.collections['province'], top_k=3)
            for s in stats:
                m = s.payload.get('metadata', {})
                context_items.append(f"Stat (จ.{m.get('province')}): {m.get('total_schools')} Schools, {m.get('total_teachers')} Teachers")

            context_str = "\n".join(context_items)
            
            # 2. Generate Answer with Gemini
            prompt = f"""
            Role: You are DO-MOE (น้องดีโอ), a friendly education assistant from Thailand's Ministry of Education.
            Goal: Answer the user's question using the provided context.
            
            Context from Database:
            {context_str}
            
            User Question: "{query}"
            
            Instructions:
            - Answer naturally in Thai with a friendly tone.
            - If context contains the answer, use it.
            - If context is irrelevant or you cannot answer, suggest the user switch to "หมวดทั่วไป" (General category) for better assistance.
            - Be helpful, friendly, and speak as "น้องดีโอ".
            """
            
            response = self.model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            logger.error(f"RAG Fallback failed: {e}")
            # Even on error, suggest category switch instead of generic error
            return (
                "😊 ขออภัยครับ น้องดีโอไม่พบข้อมูลที่ตรงกับคำถามนี้ในฐานข้อมูลการศึกษาครับ\n\n"
                "💡 **แนะนำ:** ลองสลับไปหมวด **\"ทั่วไป\"** ในแถบด้านซ้าย น้องดีโออาจช่วยเหลือได้มากกว่าครับ! ✨"
            )


    def chat(self, message: str, history: List[Dict[str, str]] = None) -> Generator[Tuple[List[Dict[str, str]], str], None, None]:
        """Main chat interface"""
        if history is None:
            history = []
            
        # Add user message to history effectively immediately
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": ""}) # Placeholder
        
        # 🛡️ INPUT SANITIZATION (Security)
        sanitized_message, error = input_sanitizer.sanitize(message)
        if error:
            history[-1]["content"] = error
            yield history, ""
            return
        message = sanitized_message  # Use sanitized version
        
        # Check if it's a "reset" command
        if message.lower() in ['reset', 'clear', 'ล้าง', 'เริ่มใหม่']:
            self.memory.clear()
            history[-1]["content"] = "ล้างความจำเรียบร้อยครับ เริ่มต้นใหม่ได้เลย! ✨"
            yield history, ""
            return
        
        logger.info(f"💬 User: {message}")
        
        # ⚡ 0. Check Semantic Cache for Instant Reply
        cached_response = self.cache.check(message)
        if cached_response:
            history[-1]["content"] = cached_response
            yield history, ""
            return

        # Parse query intent
        parsed = self.parser.parse(message)
        
        # Apply context from previous questions (for follow-up questions like "แล้วปัตตานีละ")
        parsed = self.memory.apply_context(parsed, message)
        
        # Update memory with current query context
        self.memory.update(parsed)
        
        logger.info(f"🎯 Intent: {parsed.intent.value}, Level: {parsed.level.value}")
        logger.info(f"   Region: {parsed.region}, Province: {parsed.province}")
        
        # ============================================================
        # CHECK FOR GENERAL/GREETING QUERIES IN NON-GENERAL CATEGORIES
        # Logic: Use LLM to classify if query is General or Education
        # ============================================================
        current_category = getattr(self, '_current_category', 'general')
        is_non_general_category = current_category in ['school', 'student']
        
        if is_non_general_category:
            # AI Classification
            intent_type = self._classify_intent_with_llm(message)
            logger.info(f"🧠 LLM Classified Intent: {intent_type} for '{message}' (Category: {current_category})")
            
            # Additional check: If LLM says General, but we found strong education keywords, trust keywords
            EDUCATION_KEYWORDS = ['โรงเรียน', 'นักเรียน', 'ครู', 'การศึกษา', 'สพฐ', 'สช']
            has_strong_edu_keyword = any(kw in message for kw in EDUCATION_KEYWORDS)
            
            if "GENERAL" in intent_type and not has_strong_edu_keyword:
                logger.info(f"✅ Triggering category switch suggestion (AI Decision)")
                suggestion_response = f"😊 สวัสดีครับ! น้องดีโอยินดีต้อนรับค่ะ\n\n" \
                                      f"ขณะนี้คุณอยู่ในโหมด **{'โรงเรียน' if current_category == 'school' else 'นักเรียน'}** " \
                                      f"ซึ่งเหมาะสำหรับถามข้อมูลเฉพาะทาง\n\n" \
                                      f"💡 **แนะนำ**: จากคำถาม \"{message}\" ดูเหมือนจะเป็นการพูดคุยทั่วไป รบกวนสลับไปยังหมวด **\"ทั่วไป\"** ในแถบด้านซ้ายนะครับ " \
                                      f"เพื่อให้น้องดีโอช่วยเหลือได้เต็มที่ค่ะ! ✨"
                history[-1]["content"] = suggestion_response
                self.cache.save(message, suggestion_response)
                yield history, ""
                return


        
        # ============================================================
        # SPECIAL HANDLING FOR SCHOOL QUERIES
        # ============================================================
        is_school_query = parsed.intent in [
            QueryIntent.SCHOOL_SEARCH, QueryIntent.SCHOOL_LIST, 
            QueryIntent.SCHOOL_DETAIL, QueryIntent.SCHOOL_COUNT
        ]
        
        if is_school_query:
            school_engine = SchoolSearchEngine(qdrant_client)
            response_text = ""
            
            if parsed.intent == QueryIntent.SCHOOL_DETAIL:
                synthesizer = ResponseSynthesizer()
                
                # Extract school name from query or use LLM-extracted name
                school_name = parsed.school_name
                
                if not school_name:
                    # Fallback: clean query to get school name
                    query_lower = message.lower()
                    phrases_to_remove = [
                        'ข้อมูลโรงเรียน', 'รายละเอียดโรงเรียน', 'เบอร์โทรโรงเรียน',
                        'ที่อยู่โรงเรียน', 'ติดต่อโรงเรียน', 'โรงเรียน', 'ร.ร.', 'รร.',
                        'อยู่ที่ไหน', 'อยู่ตรงไหน', 'อยู่ไหน', 'ตั้งอยู่ที่ไหน',
                        'ขอข้อมูล', 'ขอรายละเอียด', 'ขอดู', 'หา', 'ค้นหา',
                        'ครับ', 'ค่ะ', 'หน่อย', 'ได้ไหม', 'มั้ย', 'บ้าง',
                        'ที่ตั้ง', 'ที่อยู่', 'ของ', 'ที่'
                    ]
                    school_name = query_lower
                    for phrase in phrases_to_remove:
                        school_name = school_name.replace(phrase, '')
                    school_name = ' '.join(school_name.split()).strip()
                
                if school_name:
                    details = school_engine.get_school_details(school_name)
                    if details:
                        # Prepare comprehensive data for LLM synthesis
                        data = {
                            "query_type": "school_detail",
                            "school": {
                                "name": details.get('school_name'),
                                "address": {
                                    "subdistrict": details.get('subdistrict'),
                                    "district": details.get('district'),
                                    "province": details.get('province'),
                                    "postcode": details.get('postcode')
                                },
                                "agency": details.get('agency'),
                                "phone": details.get('phone1') or details.get('phone2'),
                                "school_code": details.get('school_code'),
                                "has_coordinates": bool(details.get('latitude') and details.get('longitude'))
                            }
                        }
                        
                        # Try LLM synthesis for comprehensive response
                        llm_response = synthesizer.synthesize("SCHOOL_DETAIL", data, message)
                        
                        if llm_response:
                            response_text = llm_response
                        else:
                            # Fallback to structured response
                            address = f"ต.{details.get('subdistrict', '-')} อ.{details.get('district', '-')} จ.{details.get('province', '-')}"
                            response_text = f"📍 **ข้อมูลโรงเรียน{details.get('school_name')}**\n\n"
                            response_text += f"🏫 **ชื่อ**: {details.get('school_name')}\n"
                            response_text += f"📌 **ที่ตั้ง**: {address}\n"
                            response_text += f"🏛️ **สังกัด**: {details.get('agency')}\n"
                            if details.get('postcode'):
                                response_text += f"📮 **รหัสไปรษณีย์**: {details.get('postcode')}\n"
                            if details.get('phone1'):
                                response_text += f"📞 **โทรศัพท์**: {details.get('phone1')}\n"
                        
                        # Add unique feature: Map widget (ChatGPT doesn't have this!)
                        lat = details.get('latitude')
                        lng = details.get('longitude')
                        if lat and lng:
                            try:
                                lat_float = float(lat)
                                lng_float = float(lng)
                                import json
                                address = f"ต.{details.get('subdistrict', '-')} อ.{details.get('district', '-')} จ.{details.get('province', '-')}"
                                map_json = json.dumps({
                                    "latitude": lat_float,
                                    "longitude": lng_float, 
                                    "schoolName": details.get('school_name', school_name),
                                    "address": address
                                }, ensure_ascii=False)
                                response_text += f"\n<map>{map_json}</map>"
                            except:
                                pass
                        
                        # Add follow-up suggestions
                        response_text += f"\n\n💡 **คำถามที่น่าสนใจ**\n"
                        response_text += f"- รายชื่อโรงเรียนในอำเภอ{details.get('district', '')}?\n"
                        response_text += f"- จังหวัด{details.get('province', '')}มีโรงเรียนกี่แห่ง?\n"
                    else:
                        response_text = f"❌ ไม่พบข้อมูลโรงเรียน \"{school_name}\" ในฐานข้อมูล\n\n💡 ลองค้นหาด้วยชื่ออื่น เช่น \"โรงเรียนบ้าน...\" หรือ \"โรงเรียนวัด...\""
                else:
                    response_text = "❓ กรุณาระบุชื่อโรงเรียนที่ต้องการค้นหา เช่น \"ข้อมูลโรงเรียนสวนกุหลาบ\""
            
            # ========================================
            # LOAD MORE - Pagination (No LLM!)
            # ========================================
            elif parsed.intent == QueryIntent.LOAD_MORE:
                # Check if we have pagination context
                last_query = getattr(self.memory, 'last_school_list_query', None)
                current_offset = getattr(self.memory, 'last_school_list_offset', 0)
                
                if last_query and current_offset > 0:
                    province = last_query.get('province')
                    district = last_query.get('district')
                    agency = last_query.get('agency')
                    total = last_query.get('total', 0)
                    
                    # Use already-deduplicated search functions with higher limit
                    # Then slice to get the correct page
                    if district and province:
                        all_results = school_engine.search_by_district(province, district, agency, limit=total)
                    elif province:
                        all_results = school_engine.search_by_province(province, agency, limit=total)
                    else:
                        all_results = []
                    
                    # Get slice for current page
                    results = all_results[current_offset:current_offset + 15]
                    
                    if results:
                        location = f"จ.{province}" if not district else f"อ.{district} จ.{province}"
                        agency_text = f" สังกัด{agency}" if agency else ""
                        
                        response_text = f"📚 **รายชื่อโรงเรียนต่อ** ({location}{agency_text}):\n\n"
                        
                        for i, hit in enumerate(results, current_offset + 1):
                            meta = hit.payload.get('metadata', {})
                            school_name = meta.get('school_name', 'ไม่ระบุ')
                            dist = meta.get('district', '-')
                            subdistrict = meta.get('subdistrict', '-')
                            response_text += f"{i}. **{school_name}** (ต.{subdistrict}, อ.{dist})\n"
                        
                        new_offset = current_offset + len(results)
                        remaining = total - new_offset
                        
                        if remaining > 0:
                            response_text += f"\n*...และอีก {remaining:,} แห่ง*"
                            response_text += f"\n\n💡 **พิมพ์ \"ดูเพิ่มเติม\" เพื่อดูโรงเรียนต่อไป**"
                            self.memory.last_school_list_offset = new_offset
                        else:
                            response_text += f"\n\n✅ **แสดงครบทั้งหมดแล้ว!**"
                            self.memory.last_school_list_offset = 0
                            self.memory.last_school_list_query = None
                    else:
                        response_text = "✅ **แสดงครบทั้งหมดแล้ว!**"
                        self.memory.last_school_list_offset = 0
                else:
                    response_text = "❓ ไม่มีข้อมูลให้แสดงเพิ่มเติม กรุณาค้นหารายชื่อโรงเรียนใหม่ก่อน"
                    
            elif parsed.intent == QueryIntent.SCHOOL_COUNT:
                # Initialize response synthesizer
                synthesizer = ResponseSynthesizer()
                
                # Gather comprehensive data for LLM synthesis
                data = {
                    "query_type": "school_count",
                    "location": {},
                    "counts": {},
                    "sample_schools": []
                }
                
                # Priority: Province > Region (more specific wins)
                if parsed.province:
                    # Province level count (takes priority over region)
                    count = school_engine.count_schools(
                        province=parsed.province,
                        district=parsed.district,
                        agency=parsed.agency
                    )
                    
                    # Get sample schools
                    if parsed.district:
                        sample_results = school_engine.search_by_district(parsed.province, parsed.district, parsed.agency, limit=10)
                    else:
                        sample_results = school_engine.search_by_province(parsed.province, parsed.agency, limit=10)
                    
                    sample_schools = []
                    for s in sample_results:
                        meta = s.payload.get('metadata', {})
                        sample_schools.append({
                            "name": meta.get('school_name'),
                            "district": meta.get('district'),
                            "subdistrict": meta.get('subdistrict')
                        })
                    
                    data["location"] = {
                        "province": parsed.province,
                        "district": parsed.district,
                        "agency": parsed.agency
                    }
                    data["counts"] = {"total": count}
                    data["sample_schools"] = sample_schools
                    
                elif parsed.region and parsed.region != "each_region":
                    # Only use region if no province specified
                    provinces_in_region = REGIONS.get(parsed.region, [])
                    total_count = 0
                    province_breakdown = []
                    
                    for province in provinces_in_region:
                        count = school_engine.count_schools(province=province, agency=parsed.agency)
                        total_count += count
                        if count > 0:
                            province_breakdown.append({"province": province, "count": count})
                    
                    # Get sample schools from top provinces
                    sample_schools = []
                    for prov_data in sorted(province_breakdown, key=lambda x: x['count'], reverse=True)[:3]:
                        prov_schools = school_engine.search_by_province(prov_data['province'], parsed.agency, limit=3)
                        for s in prov_schools:
                            meta = s.payload.get('metadata', {})
                            sample_schools.append({
                                "name": meta.get('school_name'),
                                "province": meta.get('province'),
                                "district": meta.get('district')
                            })
                    
                    data["location"] = {"region": parsed.region, "agency": parsed.agency}
                    data["counts"] = {
                        "total": total_count,
                        "province_breakdown": sorted(province_breakdown, key=lambda x: x['count'], reverse=True)[:10]
                    }
                    data["sample_schools"] = sample_schools[:10]
                
                # Synthesize comprehensive response using LLM
                llm_response = synthesizer.synthesize("SCHOOL_COUNT", data, message)
                
                if llm_response:
                    response_text = llm_response
                else:
                    # Fallback to simple response
                    location = parsed.region or parsed.province or parsed.district or "ทั้งประเทศ"
                    agency_text = f" สังกัด{parsed.agency}" if parsed.agency else ""
                    response_text = f"📊 **{location}**{agency_text} มีโรงเรียนทั้งหมด **{data['counts'].get('total', 0):,}** แห่ง"
                
            elif parsed.intent == QueryIntent.SCHOOL_LIST:
                synthesizer = ResponseSynthesizer()
                results = []
                location = ""
                total = 0
                
                # Gather data for LLM synthesis
                data = {
                    "query_type": "school_list",
                    "location": {},
                    "total": 0,
                    "schools": [],
                    "district_breakdown": []
                }
                
                # Priority: District > Province > Region (more specific wins)
                if parsed.district and parsed.province:
                    results = school_engine.search_by_district(parsed.province, parsed.district, parsed.agency, limit=15)
                    location = f"อ.{parsed.district} จ.{parsed.province}"
                    total = school_engine.count_schools(parsed.province, parsed.district, parsed.agency)
                    data["location"] = {"province": parsed.province, "district": parsed.district, "agency": parsed.agency}
                    
                elif parsed.province:
                    # Province takes priority over region when both exist
                    results = school_engine.search_by_province(parsed.province, parsed.agency, limit=15)
                    location = f"จ.{parsed.province}"
                    total = school_engine.count_schools(parsed.province, agency=parsed.agency)
                    data["location"] = {"province": parsed.province, "agency": parsed.agency}
                    
                elif parsed.region and parsed.region != "each_region":
                    # Only use region if no province specified
                    provinces_in_region = REGIONS.get(parsed.region, [])
                    all_results = []
                    province_stats = []
                    for province in provinces_in_region:
                        province_results = school_engine.search_by_province(province, parsed.agency, limit=5)
                        count = school_engine.count_schools(province=province, agency=parsed.agency)
                        all_results.extend(province_results)
                        total += count
                        if count > 0:
                            province_stats.append({"province": province, "count": count})
                    results = all_results[:15]
                    location = parsed.region
                    data["location"] = {"region": parsed.region, "agency": parsed.agency}
                    data["district_breakdown"] = sorted(province_stats, key=lambda x: x['count'], reverse=True)[:8]
                else:
                    response_text = "❓ กรุณาระบุจังหวัด อำเภอ หรือภูมิภาคที่ต้องการค้นหา เช่น \"โรงเรียนในภาคใต้\" หรือ \"โรงเรียนในจังหวัดปัตตานี\""
                    history[-1]["content"] = response_text
                    yield history, ""
                    return
                
                # Build school list for LLM
                data["total"] = total
                for hit in results[:15]:
                    meta = hit.payload.get('metadata', {})
                    data["schools"].append({
                        "name": meta.get('school_name'),
                        "district": meta.get('district'),
                        "subdistrict": meta.get('subdistrict'),
                        "agency": meta.get('agency')
                    })
                
                if results:
                    # Try LLM synthesis
                    llm_response = synthesizer.synthesize("SCHOOL_LIST", data, message)
                    
                    if llm_response:
                        response_text = llm_response
                        # Add unique feature: Load More hint
                        if total > 15:
                            response_text += f"\n\n💡 **พิมพ์ \"ดูเพิ่มเติม\" เพื่อดูโรงเรียนต่อไป** (เหลืออีก {total - 15:,} แห่ง)"
                    else:
                        # Fallback to simple response
                        response_text = f"📊 **{location}** มีโรงเรียนทั้งหมด **{total:,}** แห่ง\n\n📚 **รายชื่อ:**\n"
                        for i, hit in enumerate(results[:15], 1):
                            meta = hit.payload.get('metadata', {})
                            response_text += f"{i}. **{meta.get('school_name')}** (อ.{meta.get('district')})\n"
                    
                    # Save pagination context
                    if total > 15:
                        self.memory.last_school_list_offset = 15
                        self.memory.last_school_list_query = {
                            'province': parsed.province,
                            'district': parsed.district,
                            'agency': parsed.agency,
                            'region': parsed.region,
                            'total': total
                        }
                else:
                    response_text = f"❌ ไม่พบโรงเรียนใน{location}"
                    
            elif parsed.intent == QueryIntent.SCHOOL_SEARCH:
                # If region or province is specified without school name, redirect to SCHOOL_LIST
                if (parsed.region or parsed.province) and not parsed.school_name:
                    logger.info(f"🔄 SCHOOL_SEARCH with region/province → redirecting to SCHOOL_LIST logic")
                    # Reuse SCHOOL_LIST handler logic
                    parsed.intent = QueryIntent.SCHOOL_LIST
                    # Continue to SCHOOL_LIST handler by not returning here and letting flow continue
                    # But since we're in elif, we need to handle it here directly
                    synthesizer = ResponseSynthesizer()
                    results = []
                    location = ""
                    total = 0
                    data = {"query_type": "school_list", "location": {}, "total": 0, "schools": [], "district_breakdown": []}
                    
                    if parsed.province:
                        results = school_engine.search_by_province(parsed.province, parsed.agency, limit=15)
                        location = f"จ.{parsed.province}"
                        total = school_engine.count_schools(parsed.province, agency=parsed.agency)
                        data["location"] = {"province": parsed.province, "agency": parsed.agency}
                    elif parsed.region and parsed.region != "each_region":
                        provinces_in_region = REGIONS.get(parsed.region, [])
                        all_results = []
                        for province in provinces_in_region:
                            province_results = school_engine.search_by_province(province, parsed.agency, limit=5)
                            all_results.extend(province_results)
                            total += school_engine.count_schools(province=province, agency=parsed.agency)
                        results = all_results[:15]
                        location = parsed.region
                        data["location"] = {"region": parsed.region, "agency": parsed.agency}
                    
                    data["total"] = total
                    for hit in results[:15]:
                        meta = hit.payload.get('metadata', {})
                        data["schools"].append({"name": meta.get('school_name'), "district": meta.get('district'), "subdistrict": meta.get('subdistrict'), "agency": meta.get('agency')})
                    
                    if results:
                        llm_response = synthesizer.synthesize("SCHOOL_LIST", data, message)
                        if llm_response:
                            response_text = llm_response
                            if total > 15:
                                response_text += f"\n\n💡 **พิมพ์ \"ดูเพิ่มเติม\" เพื่อดูโรงเรียนต่อไป** (เหลืออีก {total - 15:,} แห่ง)"
                        else:
                            response_text = f"📊 **{location}** มีโรงเรียนทั้งหมด **{total:,}** แห่ง"
                    else:
                        response_text = f"❌ ไม่พบโรงเรียนใน{location}"
                else:
                    # Original SCHOOL_SEARCH logic - search by name
                    # 1. Advanced Cleaning: Remove intent keywords and semantic noise (brackets)
                    clean_name = message
                    remove_phrases = [
                        'หาโรงเรียน', 'ค้นหาโรงเรียน', 'โรงเรียน', 
                        'ขอรายละเอียด', 'รายละเอียด', 'ขอข้อมูล', 'ข้อมูล', 
                        'ขอเบอร์โทร', 'เบอร์โทร', 'ที่อยู่', 'รบกวนขอ', 'ขอ',
                        'ช่วยหา', 'หา', 'ให้หน่อย', 'หน่อย', 'ครับ', 'ค่ะ',
                        'สพฐ', 'อปท', 'เอกชน', 'กทม', 'ภาคใต้', 'ภาคเหนือ', 'ภาคอีสาน', 'ภาคกลาง', 'ภาคตะวันออก'
                    ]
                    for phrase in remove_phrases:
                        clean_name = clean_name.replace(phrase, '')
                    
                    # Remove content in brackets (e.g., address info)
                    clean_name = re.sub(r'[\(\[].*?[\)\]]', '', clean_name).strip()
                    
                    school_name = clean_name
                    
                    if school_name and len(school_name) > 2:
                    results = school_engine.search_by_name(school_name, limit=10)
                    if results:
                        response_text = f"🔍 **ผลการค้นหา \"{school_name}\"**\n\n"
                        for i, hit in enumerate(results[:10], 1):
                            meta = hit.payload.get('metadata', {})
                            name = meta.get('school_name', 'ไม่ระบุ')
                            province = meta.get('province', '-')
                            district = meta.get('district', '-')
                            agency = meta.get('agency', '-')
                            response_text += f"{i}. **{name}**\n   📍 อ.{district} จ.{province}\n   🏢 {agency[:20]}...\n\n"
                            
                            # Add Map Visualization Trigger if single result or top result is strong
                            if i == 1:
                                try:
                                    lat = float(meta.get('latitude', 0))
                                    lon = float(meta.get('longitude', 0))
                                    if lat and lon:
                                        map_data = {
                                            "lat": lat,
                                            "lon": lon,
                                            "name": name,
                                            "info": f"อ.{district} จ.{province}"
                                        }
                                        import json
                                        map_json = json.dumps(map_data, ensure_ascii=False)
                                        response_text += f"\n<map>{map_json}</map>"
                                except:
                                    pass
                    else:
                        # 🔤 TYPO TOLERANCE: Try fuzzy matching first
                        logger.info(f"⚠️ School search failed for '{school_name}', trying fuzzy match...")
                        similar_schools = school_engine.find_similar_schools(school_name, province=parsed.province, top_k=5)
                        
                        if similar_schools:
                            # Show "Did You Mean?" suggestions
                            response_text = f"🤔 **คุณหมายถึง...?** (ไม่พบ \"{school_name}\" ตรงๆ)\n\n"
                            response_text += "📋 **โรงเรียนที่ใกล้เคียง:**\n"
                            for i, school in enumerate(similar_schools, 1):
                                score_pct = int(school['score'] * 100)
                                response_text += f"{i}. **{school['name']}** ({score_pct}% ตรงกัน)\n"
                                response_text += f"   📍 อ.{school['district']} จ.{school['province']}\n\n"
                            response_text += "\n💡 *ลองคลิกหรือพิมพ์ชื่อที่ถูกต้องอีกครั้งนะครับ*"
                            
                            history[-1]["content"] = response_text
                            self.cache.save(message, response_text)
                            yield history, ""
                            return
                        else:
                            # 🚀 FALLBACK: No similar schools found, use RAG
                            logger.info(f"⚠️ No similar schools found, triggering RAG fallback...")
                            fallback_resp = self._rag_fallback(message)
                            history[-1]["content"] = fallback_resp
                            self.cache.save(message, fallback_resp)
                            yield history, ""
                            return
                else:
                    # If name is empty after cleaning (e.g. just "ขอรายละเอียด"), try RAG anyway
                    fallback_resp = self._rag_fallback(message)
                    history[-1]["content"] = fallback_resp
                    self.cache.save(message, fallback_resp)
                    yield history, ""
                    return
            
            # Cache and return response
            history[-1]["content"] = response_text
            self.cache.save(message, response_text)
            yield history, ""
            return
        
        # ============================================================
        # SPECIAL HANDLING FOR RANKING QUERIES
        # ============================================================
        is_ranking = parsed.intent in [QueryIntent.RANKING_MOST, QueryIntent.RANKING_LEAST]
        
        if is_ranking:
            # Determine the correct level based on query context
            query_lower = message.lower()
            
            # 2. Check explicitly for "Agency Ranking" (สังกัดไหน/สังกัดอะไร)
            # We process this BEFORE generic ranking to set the correct level
            agency_ranking_kw = ['สังกัดไหน', 'สังกัดใด', 'สังกัดอะไร', 'สังกัดที่มี', 
                                 'หน่วยงานไหน', 'หน่วยงานใด', 'หน่วยงานอะไร',
                                 'สังกัดการศึกษา']  # Added more keywords
            
            is_agency_within_province = False  # Track this special case
            
            if any(kw in query_lower for kw in agency_ranking_kw):
                # Special case: "สังกัดไหนในจังหวัดX" → use PROVINCE collection, aggregate by agency
                if parsed.province:
                    logger.info(f"   Agency ranking within province: {parsed.province}")
                    search_level = QueryLevel.PROVINCE
                    is_agency_within_province = True  # Flag for special aggregation
                elif parsed.region:
                    # "สังกัดไหนในภาคX" → use PROVINCE collection, aggregate by agency
                    logger.info(f"   Agency ranking within region: {parsed.region}")
                    search_level = QueryLevel.PROVINCE  # Use province collection which has province field for filtering
                else:
                    search_level = QueryLevel.AGENCY
            # "จังหวัดไหน" → search in province collection
            elif 'จังหวัดไหน' in query_lower or 'จังหวัดใด' in query_lower:
                search_level = QueryLevel.PROVINCE
            # "อำเภอไหน" → search in district collection  
            elif 'อำเภอไหน' in query_lower or 'อำเภอใด' in query_lower or 'เขตไหน' in query_lower:
                search_level = QueryLevel.DISTRICT
            # "ตำบลไหน" → search in subdistrict collection
            elif 'ตำบลไหน' in query_lower or 'ตำบลใด' in query_lower or 'แขวงไหน' in query_lower:
                search_level = QueryLevel.SUBDISTRICT
            else:
                # Default based on parsed level
                search_level = parsed.level
            
            logger.info(f"🏆 Ranking query detected, search_level: {search_level.value}")
            
            # Update parsed query's level for correct formatting
            parsed.level = search_level
            
            collection_name = self.collections.get(search_level.value)
            if not collection_name:
                history[-1]["content"] = f"❌ ไม่พบฐานข้อมูลระดับ {search_level.value}"
                yield history, ""
                return
            
            # Use ranking_search for these queries
            # NOTE: Removed robotic message per user feedback
            # history[-1]["content"] = f"🏆 กำลังค้นหาอันดับใน {search_level.value}..."
            # yield history, ""
            
            results = self.search_engine.ranking_search(parsed, collection_name)
        
        # ============================================================
        # SPECIAL HANDLING FOR COMPARISON QUERIES
        # ============================================================
        elif parsed.intent == QueryIntent.COMPARE:
            logger.info("⚖️ Comparison query detected")
            
            # Extract multiple provinces from query
            query_lower = message.lower()
            provinces_found = []
            for province in THAI_PROVINCES:
                if province.lower() in query_lower:
                    provinces_found.append(province)
            
            if len(provinces_found) >= 2:
                # Compare multiple provinces
                collection_name = self.collections.get('province')
                # history[-1]["content"] = f"⚖️ กำลังเปรียบเทียบ {len(provinces_found)} จังหวัด..."
                # yield history, ""
                
                all_results = []
                for prov in provinces_found:
                    temp_parsed = ParsedQuery(
                        intent=QueryIntent.COUNT,
                        level=QueryLevel.PROVINCE,
                        province=prov,
                        original_query=message,
                        normalized_query=message
                    )
                    res = self.search_engine.search(temp_parsed, collection_name)
                    all_results.extend(res)
                
                results = all_results
                parsed.level = QueryLevel.PROVINCE
            else:
                # If can't find multiple provinces, fall back to normal search
                collection_name = self.collections.get(parsed.level.value)
                if not collection_name:
                    history[-1]["content"] = f"❌ ไม่พบฐานข้อมูลระดับ {parsed.level.value}"
                    yield history, ""
                    return
                
                # history[-1]["content"] = f"🔍 ค้นหาใน {parsed.level.value}..."
                # yield history, ""
                results = self.search_engine.search(parsed, collection_name)
        
        else:
            # Normal search for non-ranking queries
            collection_name = self.collections.get(parsed.level.value)
            
            # If collection not found OR Intent is UNKNOWN -> RAG Fallback
            if not collection_name or parsed.intent == QueryIntent.UNKNOWN:
                fallback_resp = self._rag_fallback(message)
                history[-1]["content"] = fallback_resp
                self.cache.save(message, fallback_resp)
                yield history, ""
                return
            
            # Special handling for "Each Region"
            if parsed.region == "each_region":
                logger.info("🌍 Each-region query detected, searching all provinces")
                # IMPORTANT: Clear location filters to fetch ALL data
                parsed.province = None
                parsed.district = None
                parsed.subdistrict = None
                results = self.search_engine.search(parsed, self.collections.get('province'), top_k=200)
            else:
                results = self.search_engine.search(parsed, collection_name)
                
            # 🚀 CHECK FOR EMPTY RESULTS -> TRIGGER RAG FALLBACK
            if not results:
                logger.info("⚠️ No exact matches found, triggering RAG Fallback...")
                fallback_resp = self._rag_fallback(message)
                history[-1]["content"] = fallback_resp
                self.cache.save(message, fallback_resp)
                yield history, ""
                return
        
        # EARLY EXIT REMOVED TO SUPPORT GENERAL KNOWLEDGE FALLBACK
        # if not results: ...
        
        # Aggregate - use special method for agency ranking within province
        is_least = parsed.intent == QueryIntent.RANKING_LEAST
        
        # Check if this is an agency ranking query
        query_lower = message.lower()
        agency_ranking_kw = ['สังกัดไหน', 'สังกัดใด', 'สังกัดอะไร', 'สังกัดที่มี', 
                             'หน่วยงานไหน', 'หน่วยงานใด', 'หน่วยงานอะไร',
                             'สังกัดการศึกษา']  # Added more keywords
        is_agency_ranking = (
            parsed.intent in [QueryIntent.RANKING_MOST, QueryIntent.RANKING_LEAST] and
            any(kw in query_lower for kw in agency_ranking_kw)
        )
        
        if is_agency_ranking:
            # Agency ranking within province OR region
            if parsed.province:
                aggregated = self.aggregator.aggregate_by_agency(results, province=parsed.province, is_least=is_least)
            elif parsed.region and parsed.region != "each_region":
                aggregated = self.aggregator.aggregate_by_agency(results, region=parsed.region, is_least=is_least)
            else:
                # Agency ranking nationwide (no filter)
                aggregated = self.aggregator.aggregate_by_agency(results, is_least=is_least)
        elif parsed.region == "each_region":
            aggregated = self.aggregator.aggregate_by_region(results, is_least)
        else:
            aggregated = self.aggregator.aggregate(results, parsed.level, is_least)
        
        # Format response
        history[-1]["content"] = ""
        full_response = ""
        for chunk in self.formatter.format(aggregated, parsed):
            full_response += chunk
            history[-1]["content"] = full_response
            yield history, ""
        
        # Add source info (Only if we actually used the DB)
        if results:
            source_info = f"\n\n---\n*ข้อมูลจาก: {collection_name} ({len(results)} รายการ)*"
            history[-1]["content"] += source_info
            full_response += source_info
            
        # 💾 Save successful response to Cache
        self.cache.save(message, full_response)
        
        yield history, ""


# =====================================================================
# GRADIO UI
# =====================================================================
def create_gradio_ui() -> Optional['gr.Blocks']:
    """Create Gradio interface"""
    if not GRADIO_AVAILABLE:
        logger.error("Gradio not available")
        return None
    
    chatbot = EducationChatbot()
    
    with gr.Blocks(title="🎓 DO-MOE Education Chatbot v5.0") as demo:
        gr.Markdown("""
        # 🎓 แชทบอท DO-MOE กระทรวงศึกษาธิการ v5.0
        ### ✨ Production Ready - รองรับทุกประเภทคำถาม
        """)
        
        with gr.Row():
            with gr.Column(scale=3):
                chatbox = gr.Chatbot(label="💬 การสนทนา", height=500, type="messages")
                
                with gr.Row():
                    msg = gr.Textbox(
                        placeholder="ถามอะไรก็ได้เกี่ยวกับโรงเรียนในไทย...",
                        scale=9, show_label=False, lines=1
                    )
                    submit = gr.Button("📤 ส่ง", variant="primary", scale=1)
                
                clear = gr.Button("🗑️ ล้างประวัติ", size="sm")
            
            with gr.Column(scale=1):
                gr.Markdown("""
                ### 💡 ตัวอย่างคำถาม
                
                **📊 นับจำนวน:**
                - ปัตตานีมีกี่โรงเรียน
                - ตำบลบานา อำเภอเมืองปัตตานี
                
                **🏆 มากที่สุด:**
                - ภาคใต้จังหวัดไหนมีโรงเรียนมากที่สุด
                - อำเภอไหนในยะลามีโรงเรียนเยอะสุด
                
                **🔽 น้อยที่สุด:**
                - ยะลาอำเภอไหนมีโรงเรียนน้อยที่สุด
                - ตำบลไหนมีโรงเรียนน้อยสุด
                
                **🔍 ค้นหา:**
                - เวียง เชียงแสน
                - ดอยลาน เมืองเชียงราย
                """)
        
        def respond(message, history):
            for hist, _ in chatbot.chat(message, history):
                yield hist, ""
        
        msg.submit(respond, [msg, chatbox], [chatbox, msg]).then(lambda: "", None, msg)
        submit.click(respond, [msg, chatbox], [chatbox, msg]).then(lambda: "", None, msg)
        clear.click(lambda: [], None, chatbox)
    
    return demo


# =====================================================================
# FLASK API
# =====================================================================
def create_flask_api():
    """Create Flask API for production deployment"""
    from flask import Flask, request, jsonify, Response, stream_with_context
    from flask_cors import CORS
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

    # SECURE: Rate Limiting (Prevent DDoS/Spam)
    # Uses SQLite to store hit counts (persistent across restarts)
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["1000 per day", "200 per hour"], # Increased for production
        storage_uri="memory://"
    )

    @app.after_request
    def after_request(response):
        """Global CORS header enforcement"""
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-API-Key')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response
    
    chatbot = EducationChatbot()
    
    @app.route('/api/health', methods=['GET'])
    @limiter.exempt # No limit for health check
    def health():
        return jsonify({'status': 'healthy', 'version': '5.0.0'})

    @app.route('/api/chat/stream', methods=['POST', 'OPTIONS'])
    @limiter.limit("50 per minute") # Increased limit
    def chat_stream():
        if request.method == 'OPTIONS':
            return '', 204
        """Stream chat response (Server-Sent Events)"""
        data = request.json
        message = data.get('message', '')
        history = data.get('history', [])
        session_id = data.get('session_id', 'default')
        category = data.get('category', 'general')  # NEW: Get category from request

        # Load persistence
        mem_data = session_db.get_session_data(session_id)
        if mem_data:
            memory = ConversationMemory.from_dict(mem_data)
        else:
            memory = ConversationMemory()
        
        # Inject memory & category
        chatbot.memory = memory
        chatbot._current_category = category  # NEW: Set current category
        
        def generate():
            last_len = 0
            # Manually extract context from history if needed (similar to /chat)
            if not memory.last_province and history:
                memory.extract_from_history(history)
                
            for hist, _ in chatbot.chat(message, history):
                if hist:
                    content = hist[-1].get('content', '')
                    # Calculate delta for streaming
                    delta = content[last_len:]
                    if delta:
                        # Send JSON data
                        yield f"data: {session_db.json.dumps({'text': delta}, ensure_ascii=False)}\n\n"
                        last_len = len(content)
            
            # Save memory after stream ends
            session_db.save_session_data(session_id, memory.to_dict())
            yield "data: [DONE]\n\n"
            
        return Response(stream_with_context(generate()), mimetype='text/event-stream')
    
    @app.route('/api/chat', methods=['POST'])
    @limiter.limit("20 per minute")
    def chat():
        data = request.json
        message = data.get('message', '')
        history = data.get('history', [])
        session_id = data.get('session_id', 'default')
        category = data.get('category', 'general')  # NEW: Get category from request
        
        # Get or create session memory (Persistent)
        mem_data = session_db.get_session_data(session_id)
        if mem_data:
            memory = ConversationMemory.from_dict(mem_data)
        else:
            memory = ConversationMemory()
            logger.info(f"🆕 Created new session memory: {session_id}")
        
        # Extract context from history if memory is empty
        if not memory.last_province and history:
            memory.extract_from_history(history)
            logger.info(f"📚 Extracted context from history: {memory}")
        
        # Use chatbot with session memory & category
        chatbot.memory = memory  # Inject session memory
        chatbot._current_category = category  # NEW: Set current category
        
        response_text = ""
        for hist, _ in chatbot.chat(message, history):
            if hist:
                response_text = hist[-1].get('content', '')
        
        # Log and Save memory state
        logger.info(f"💾 Session {session_id} memory after chat: {memory}")
        session_db.save_session_data(session_id, memory.to_dict())
        
        return jsonify({
            'success': True,
            'response': response_text,
            'history': hist,
            'memory': {
                'province': memory.last_province,
                'district': memory.last_district,
                'agency': memory.last_agency
            }
        })

    @app.route('/api/sessions', methods=['GET'])
    def list_sessions():
        """Admin endpoint to list all active sessions"""
        # In production, add auth check here
        try:
            limit = request.args.get('limit', 50)
            conn = session_db.sqlite3.connect(session_db.DB_PATH)
            conn.row_factory = session_db.sqlite3.Row
            c = conn.cursor()
            
            c.execute("""
                SELECT session_id, memory_json, updated_at 
                FROM sessions 
                ORDER BY updated_at DESC 
                LIMIT ?
            """, (limit,))
            
            rows = c.fetchall()
            conn.close()
            
            results = []
            for row in rows:
                mem = session_db.json.loads(row['memory_json'])
                results.append({
                    'id': row['session_id'],
                    'updated_at': row['updated_at'],
                    'province': mem.get('last_province'),
                    'agency': mem.get('last_agency'),
                    'last_query': mem.get('last_query')
                })
                
            return jsonify({'success': True, 'sessions': results})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    
    # ========================================================================
    # API KEY SYNC FROM ADMIN PANEL
    # ========================================================================
    @app.route('/api/sync-config', methods=['POST', 'OPTIONS'])
    def sync_config():
        """
        Receives API keys from Admin Panel and saves to shared_config.json.
        This allows Admin Panel to sync settings to Backend without Firestore.
        """
        if request.method == 'OPTIONS':
            return '', 204
        
        import json as json_module
        from pathlib import Path
        
        try:
            data = request.json
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400
            
            config_path = Path(__file__).parent / 'shared_config.json'
            
            # Save config to file
            with open(config_path, 'w', encoding='utf-8') as f:
                json_module.dump(data, f, ensure_ascii=False, indent=2)
            
            # Reload config in memory
            global GROQ_API_KEY
            api_keys = data.get('apiKeys', {})
            school_config = api_keys.get('school', {})
            groq_keys = school_config.get('groqKeys', [])
            
            if groq_keys:
                GROQ_API_KEY = groq_keys[0]
                logger.info(f"✅ Synced Groq API Key from Admin Panel")
            
            logger.info(f"✅ Config synced to {config_path}")
            return jsonify({
                'success': True, 
                'message': 'Config synced successfully',
                'path': str(config_path)
            })
        except Exception as e:
            logger.error(f"❌ Config sync failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # ========================================================================
    # SCHOOL PAGINATION API (No LLM - Direct Database Query)
    # ========================================================================
    @app.route('/api/schools/list', methods=['POST', 'OPTIONS'])
    def schools_list():
        """
        Paginated school list - queries Qdrant directly without LLM.
        Used by "Load More" button in frontend. (Deduplicated by school_code)
        """
        if request.method == 'OPTIONS':
            return '', 204
        
        try:
            data = request.json or {}
            province = data.get('province')
            district = data.get('district')
            agency = data.get('agency')
            offset = data.get('offset', 0)
            limit = data.get('limit', 15)
            
            if not province:
                return jsonify({'success': False, 'error': 'Province is required'}), 400
            
            # Build filter conditions
            conditions = [
                FieldCondition(key="metadata.province", match=MatchValue(value=province))
            ]
            if agency:
                conditions.append(
                    FieldCondition(key="metadata.agency", match=MatchValue(value=agency))
                )
            if district:
                conditions.append(
                    FieldCondition(key="metadata.district", match=MatchValue(value=district))
                )
            
            # Scroll through all and deduplicate by school_code
            scroll_filter = Filter(must=conditions)
            all_unique_codes = set()
            unique_schools = []
            scroll_offset = None
            
            while True:
                response = qdrant_client.scroll(
                    collection_name=COLLECTIONS["schools"],
                    scroll_filter=scroll_filter,
                    offset=scroll_offset,
                    limit=500,
                    with_payload=True
                )
                points, next_offset = response
                
                if not points:
                    break
                    
                for point in points:
                    meta = point.payload.get('metadata', {})
                    code = meta.get('school_code')
                    if code and code not in all_unique_codes:
                        all_unique_codes.add(code)
                        unique_schools.append({
                            'name': meta.get('school_name', 'ไม่ระบุ'),
                            'province': meta.get('province', '-'),
                            'district': meta.get('district', '-'),
                            'subdistrict': meta.get('subdistrict', '-'),
                            'agency': meta.get('agency', '-'),
                        })
                
                if next_offset is None:
                    break
                scroll_offset = next_offset
            
            total = len(unique_schools)
            paged_schools = unique_schools[offset:offset + limit]
            
            return jsonify({
                'success': True,
                'schools': paged_schools,
                'total': total,
                'offset': offset,
                'limit': limit,
                'hasMore': offset + len(paged_schools) < total,
                'query': {
                    'province': province,
                    'district': district,
                    'agency': agency
                }
            })
            
        except Exception as e:
            logger.error(f"❌ Schools list error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    return app


# =====================================================================
# MAIN
# =====================================================================
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="DO-MOE Education Chatbot v5.0")
    parser.add_argument('--port', type=int, default=7860)
    parser.add_argument('--host', type=str, default="0.0.0.0")
    parser.add_argument('--share', action='store_true')
    parser.add_argument('--api', action='store_true', help='Run as Flask API')
    
    args = parser.parse_args()
    
    if not GEMINI_API_KEY:
        logger.error("❌ GEMINI_API_KEY not found!")
        return
    
    print(f"""
{'='*80}
🚀 DO-MOE Education Chatbot v5.0 (Production)
{'='*80}

✅ Features:
   - Full Query Support (มากที่สุด/น้อยที่สุด/เปรียบเทียบ)
   - Smart Entity Extraction (จังหวัด/อำเภอ/ตำบล)
   - Fuzzy Matching (ค้นหาใกล้เคียง)
   - Production-grade Error Handling

🌐 Server: {args.host}:{args.port}
{'='*80}
    """)
    
    if args.api:
        app = create_flask_api()
        app.run(host=args.host, port=args.port)
    else:
        demo = create_gradio_ui()
        if demo:
            demo.launch(
                server_name=args.host,
                server_port=args.port,
                share=args.share,
                show_error=True
            )


if __name__ == "__main__":
    main()
