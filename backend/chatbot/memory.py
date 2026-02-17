"""
Conversation Memory for Education Chatbot
Handles context retention across chat turns
"""

import logging
import time
from typing import Optional, Dict, List, Any

from .types import ParsedQuery, QueryIntent, QueryLevel
from .constants import THAI_PROVINCES, REGIONS

logger = logging.getLogger(__name__)


class ConversationMemory:
    """Enhanced memory to retain context from previous questions"""

    CONTEXT_TTL_SEC = 20 * 60  # 20 minutes
    
    def __init__(self):
        self.last_province: Optional[str] = None
        self.last_region: Optional[str] = None
        self.last_district: Optional[str] = None
        self.last_intent: Optional[QueryIntent] = None
        self.last_level: Optional[QueryLevel] = None
        self.last_agency: Optional[str] = None
        self.last_query: Optional[str] = None
        self.last_school_name: Optional[str] = None  # NEW: For school-specific queries
        self.last_scope_type: Optional[str] = None
        self.last_scope_value: Optional[str] = None
        self.last_updated_at: Optional[float] = None
        # Disambiguation state (for multi-turn school selection)
        self.last_disambig_choices: Optional[List[Dict[str, str]]] = None  # [{"name": ..., "province": ...}]
        self.last_disambig_query: Optional[str] = None  # Original query that triggered disambiguation
        self.last_ai_response: Optional[str] = None  # Last assistant response text
    
    def update(self, parsed: ParsedQuery, original_query: str = None):
        """Update memory with new parsed query"""
        # Decay old context if stale
        now = time.time()
        if self.last_updated_at and now - self.last_updated_at > self.CONTEXT_TTL_SEC:
            self.clear()

        # Detect explicit scope changes and clear conflicting context
        if parsed.region and parsed.region != self.last_region:
            self.last_province = None
            self.last_district = None
            self.last_school_name = None
        if parsed.province and parsed.province != self.last_province:
            self.last_district = None
            self.last_school_name = None
        if parsed.district and parsed.district != self.last_district:
            self.last_school_name = None
        if parsed.school_name and parsed.school_name != self.last_school_name:
            # If user specifies a new school without explicit location, avoid stale location leak
            if not parsed.province:
                self.last_province = None
            if not parsed.region:
                self.last_region = None
            if not parsed.district:
                self.last_district = None

        if parsed.province:
            # Guard: province might be a list (e.g. compare queries)
            province_val = parsed.province
            if isinstance(province_val, list):
                province_val = province_val[0] if province_val else None
            if province_val:
                # Guard: sometimes region strings slip into province
                if province_val in REGIONS and not parsed.region:
                    self.last_region = province_val
                    self.last_province = None
                else:
                    self.last_province = province_val
        if parsed.region:
            self.last_region = parsed.region
        if parsed.district:
            self.last_district = parsed.district
        if parsed.intent:
            self.last_intent = parsed.intent
        if parsed.level:
            self.last_level = parsed.level
        if parsed.agency:
            self.last_agency = parsed.agency
        if parsed.school_name:
             self.last_school_name = parsed.school_name
        if original_query:
            self.last_query = original_query

        # Scope tracking (most specific wins)
        scope_type = None
        scope_value = None
        if parsed.school_name:
            scope_type = "school"
            scope_value = parsed.school_name
        elif parsed.district:
            scope_type = "district"
            scope_value = parsed.district
        elif parsed.province:
            scope_type = "province"
            scope_value = parsed.province
        elif parsed.region:
            scope_type = "region"
            scope_value = parsed.region

        if scope_type:
            self.last_scope_type = scope_type
            self.last_scope_value = scope_value
            self.last_updated_at = now
    
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

            # Extract region from previous messages
            for region in REGIONS.keys():
                if region in content:
                    self.last_region = region
                    logger.info(f"   🧭 Extracted region from history: {region}")
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
        if self.last_province or self.last_region or self.last_district or self.last_school_name:
            self.last_updated_at = time.time()
    
    def apply_context(self, parsed: ParsedQuery, query: str) -> ParsedQuery:
        """Apply context from memory to current query if needed"""
        # Clear stale context
        if self.last_updated_at and time.time() - self.last_updated_at > self.CONTEXT_TTL_SEC:
            logger.info("🧹 Context expired - clearing memory")
            self.clear()
            return parsed

        query_lower = query.lower()
        
        # Enhanced follow-up patterns
        follow_up_patterns = [
            'แล้ว', 'ละ', 'ล่ะ', 'หล่ะ', 'เหมือนกัน', 'เดียวกัน',
            'ขอ', 'ทั้งหมด', 'ทุก', 'อีก', 'ต่อ', 'เพิ่ม', 'อื่น',
            'รวม', 'สรุป', 'ทั้งนั้น', 'หมด', 'บ้าง'
        ]
        
        # Check if this looks like a follow-up question
        is_short_query = len(query) < 50
        has_follow_up_word = any(p in query_lower for p in follow_up_patterns)
        lacks_location = not parsed.province and not parsed.district
        is_global_ranking_query = ("จังหวัด" in query_lower) and any(p in query_lower for p in ["อันดับ", "จัดอันดับ", "มากที่สุด", "น้อยที่สุด", "สูงที่สุด", "ต่ำที่สุด"])
        
        # Detect "ทุกสังกัด" or "ทั้งหมด" type queries
        is_all_agencies_query = any(p in query_lower for p in ['ทุกสังกัด', 'ทั้งหมด', 'สังกัดอื่น', 'ทุกหน่วยงาน', 'ทั้งนั้น'])

        is_follow_up = is_short_query and (has_follow_up_word or lacks_location) and not is_global_ranking_query
        
        if is_follow_up and (self.last_province or self.last_region):
            logger.info(f"🔄 Follow-up question detected: '{query}'")
            logger.info(f"   Memory: province={self.last_province}, region={self.last_region}, district={self.last_district}, agency={self.last_agency}")
            
            # Apply stored province if current query doesn't have one AND doesn't have a region
            # BUT: If user only asks about agency (e.g., "สพฐ มีกี่โรงเรียน"), don't apply province - they want nationwide
            # CRITICAL FIX: If user mentions a NEW school name, DON'T apply province from memory
            #               This prevents searching "โรงเรียนในปัตตานี" using memory province "นราธิวาส"
            is_agency_only_query = parsed.agency and not parsed.province and not parsed.region
            has_new_school_name = parsed.school_name is not None  # User specified a school in this query
            
            if has_new_school_name:
                # User is asking about a specific school - search globally, don't use memory province
                logger.info(f"   🏫 New school name detected: '{parsed.school_name}' - skipping province memory for accurate search")
            elif not parsed.province and not parsed.region and self.last_province and not is_agency_only_query:
                if self.last_province in REGIONS:
                    parsed.region = self.last_province
                    logger.info(f"   ✅ Applied region from memory (was province): {self.last_province}")
                else:
                    parsed.province = self.last_province
                    logger.info(f"   ✅ Applied province from memory: {self.last_province}")
            elif not parsed.province and not parsed.region and self.last_region and not is_agency_only_query:
                parsed.region = self.last_region
                logger.info(f"   ✅ Applied region from memory: {self.last_region}")
            elif is_agency_only_query:
                logger.info(f"   ℹ️ Agency-only query detected - skipping province memory for nationwide results")
            elif parsed.region:
                logger.info(f"   ℹ️ Region query detected - skipping province memory")
            
            # Apply stored district if relevant
            if not parsed.district and self.last_district:
                parsed.district = self.last_district
                logger.info(f"   ✅ Applied district from memory: {self.last_district}")
            
            # For "ทุกสังกัด" queries, clear agency filter to get all
            if is_all_agencies_query:
                parsed.agency = None
                parsed.level = QueryLevel.PROVINCE
                parsed.intent = QueryIntent.COUNT
                logger.info(f"   ✅ All-agencies query: cleared agency filter")
            
            # Keep the same intent/level if current one is generic
            if self.last_intent and parsed.intent == QueryIntent.COUNT:
                parsed.intent = self.last_intent
                logger.info(f"   ✅ Applied intent: {self.last_intent.value}")
        
        # NEW: Restore school name context
        # If we have a stored school name, and the user hasn't specified a new one.
        # We allow restoration if location is empty OR matches the memory (consistent context).
        province_safe = not parsed.province or (self.last_province and parsed.province == self.last_province)
        region_safe = not parsed.region or (self.last_region and parsed.region == self.last_region)
        
        if self.last_school_name and not parsed.school_name and province_safe and region_safe:
             if not is_global_ranking_query:
                 parsed.school_name = self.last_school_name
                 logger.info(f"   🏫 Applied school name from memory: {self.last_school_name}")
        
        return parsed
    
    def clear(self):
        """Clear all memory"""
        self.last_province = None
        self.last_region = None
        self.last_district = None
        self.last_intent = None
        self.last_level = None
        self.last_agency = None
        self.last_query = None
        self.last_school_name = None
        self.last_scope_type = None
        self.last_scope_value = None
        self.last_updated_at = None
        self.last_disambig_choices = None
        self.last_disambig_query = None
        self.last_ai_response = None
    
    def __repr__(self):
        return f"Memory(province={self.last_province}, region={self.last_region}, district={self.last_district}, agency={self.last_agency}, scope={self.last_scope_type}:{self.last_scope_value})"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize memory to dictionary"""
        return {
            'last_province': self.last_province,
            'last_region': self.last_region,
            'last_district': self.last_district,
            'last_intent': self.last_intent.value if self.last_intent else None,
            'last_level': self.last_level.value if self.last_level else None,
            'last_agency': self.last_agency,
            'last_query': self.last_query,
            'last_school_name': self.last_school_name,
            'last_scope_type': self.last_scope_type,
            'last_scope_value': self.last_scope_value,
            'last_updated_at': self.last_updated_at,
            'last_disambig_choices': self.last_disambig_choices,
            'last_disambig_query': self.last_disambig_query,
            'last_ai_response': self.last_ai_response,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationMemory':
        """Deserialize memory from dictionary"""
        mem = cls()
        mem.last_province = data.get('last_province')
        mem.last_region = data.get('last_region')
        mem.last_district = data.get('last_district')
        mem.last_agency = data.get('last_agency')
        mem.last_query = data.get('last_query')
        mem.last_school_name = data.get('last_school_name')
        mem.last_scope_type = data.get('last_scope_type')
        mem.last_scope_value = data.get('last_scope_value')
        mem.last_updated_at = data.get('last_updated_at')
        mem.last_disambig_choices = data.get('last_disambig_choices')
        mem.last_disambig_query = data.get('last_disambig_query')
        mem.last_ai_response = data.get('last_ai_response')
        
        if data.get('last_intent'):
            try: mem.last_intent = QueryIntent(data['last_intent'])
            except: pass
            
        if data.get('last_level'):
            try: mem.last_level = QueryLevel(data['last_level'])
            except: pass
            
        return mem


# Session-based memory storage (for Flask API multi-user support)
session_memories: Dict[str, ConversationMemory] = {}


def get_or_create_memory(session_id: str) -> ConversationMemory:
    """Get or create memory for a session"""
    if session_id not in session_memories:
        session_memories[session_id] = ConversationMemory()
    return session_memories[session_id]


def clear_session_memory(session_id: str):
    """Clear memory for a session"""
    if session_id in session_memories:
        del session_memories[session_id]
