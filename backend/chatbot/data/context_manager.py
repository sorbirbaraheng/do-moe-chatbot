"""
📄 context_manager.py
📝 Advanced Context Management System
    - LLM-based context extraction (Phase 1)
    - Multi-entity tracking (Phase 2)
    - Coreference resolution (Phase 3)
    - Memory summarization (Phase 4)
"""

import logging
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class SessionContext:
    """Holds all extracted context from conversation"""
    # Multi-entity tracking (Phase 2)
    schools: List[str] = field(default_factory=list)
    provinces: List[str] = field(default_factory=list)
    districts: List[str] = field(default_factory=list)
    agencies: List[str] = field(default_factory=list)
    
    # Current focus
    current_topic: Optional[str] = None
    current_school: Optional[str] = None
    current_province: Optional[str] = None
    
    # Active Query Memory (Phase 5 - Follow-up Actions)
    last_active_query: Optional[Dict[str, Any]] = None  # { "tool": "name", "params": {...} }
    
    # Memory summarization (Phase 4)
    long_term_summary: Optional[str] = None
    
    def add_entity(self, entity_type: str, value: str):
        """Add entity to tracking list (avoid duplicates)"""
        if not value:
            return
        
        target_list = getattr(self, entity_type, None)
        if target_list is not None and value not in target_list:
            target_list.append(value)
            # Keep only last 5 entities per type
            if len(target_list) > 5:
                target_list.pop(0)
    
    def get_recent(self, entity_type: str, n: int = 2) -> List[str]:
        """Get most recent N entities of a type"""
        target_list = getattr(self, entity_type, [])
        return target_list[-n:] if target_list else []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "schools": self.schools,
            "provinces": self.provinces,
            "districts": self.districts,
            "agencies": self.agencies,
            "current_topic": self.current_topic,
            "current_school": self.current_school,
            "current_province": self.current_province,
            "last_active_query": self.last_active_query,
            "long_term_summary": self.long_term_summary
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionContext":
        """Create from dictionary"""
        ctx = cls()
        ctx.schools = data.get("schools", [])
        ctx.provinces = data.get("provinces", [])
        ctx.districts = data.get("districts", [])
        ctx.agencies = data.get("agencies", [])
        ctx.current_topic = data.get("current_topic")
        ctx.current_school = data.get("current_school")
        ctx.current_province = data.get("current_province")
        ctx.last_active_query = data.get("last_active_query")
        ctx.long_term_summary = data.get("long_term_summary")
        return ctx


class ContextManager:
    """
    Advanced Context Manager using LLM for intelligent context extraction
    Now uses Redis for persistent, shared context storage across workers.
    """
    
    # Redis key prefix for context data
    REDIS_KEY_PREFIX = "ctx:"
    CACHE_TTL = 3600  # 1 hour expiry
    
    def __init__(self, llm_client, redis_client=None):
        """
        Args:
            llm_client: MultiProviderLLM instance for LLM calls
            redis_client: Redis client for persistent storage (optional, falls back to in-memory)
        """
        self.llm = llm_client
        self.redis = redis_client
        self._fallback_cache: Dict[str, SessionContext] = {}  # Fallback if Redis unavailable
        
        if self.redis:
            logger.info("✅ ContextManager initialized with Redis storage")
        else:
            logger.warning("⚠️ ContextManager using in-memory storage (no Redis)")
    
    def get_or_create_context(self, session_id: str) -> SessionContext:
        """Get existing context from Redis or create new one"""
        cache_key = f"{self.REDIS_KEY_PREFIX}{session_id}"
        
        # Try Redis first
        if self.redis:
            try:
                cached = self.redis.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    return SessionContext.from_dict(data)
            except Exception as e:
                logger.warning(f"⚠️ Redis read failed: {e}")
        
        # Fallback to in-memory
        if session_id in self._fallback_cache:
            return self._fallback_cache[session_id]
        
        # Create new context
        return SessionContext()
    
    def save_context(self, session_id: str, context: SessionContext):
        """Save context to Redis"""
        cache_key = f"{self.REDIS_KEY_PREFIX}{session_id}"
        
        if self.redis:
            try:
                self.redis.setex(cache_key, self.CACHE_TTL, json.dumps(context.to_dict()))
            except Exception as e:
                logger.warning(f"⚠️ Redis write failed: {e}")
                # Fallback to in-memory
                self._fallback_cache[session_id] = context
        else:
            self._fallback_cache[session_id] = context

    
    def extract_context_with_llm(self, query: str, history: List[Dict], 
                                  existing_context: SessionContext) -> SessionContext:
        """
        Phase 1: Use LLM to extract structured context from conversation
        
        Args:
            query: Current user query
            history: Recent conversation history
            existing_context: Previously extracted context
        
        Returns:
            Updated SessionContext with extracted entities
        """
        # Build prompt for context extraction
        history_text = self._format_history(history[-6:])  # Last 6 messages
        existing_entities = {
            "schools": existing_context.schools[-3:],
            "provinces": existing_context.provinces[-3:],
            "current_school": existing_context.current_school,
            "current_province": existing_context.current_province
        }
        
        prompt = f"""วิเคราะห์บทสนทนาและดึง entities ที่เกี่ยวข้องกับการศึกษา

**ประวัติสนทนา:**
{history_text}

**คำถามปัจจุบัน:** "{query}"

**Context ที่รู้อยู่แล้ว:**
{json.dumps(existing_entities, ensure_ascii=False)}

**คำสั่ง:**
1. ดึงชื่อโรงเรียน, จังหวัด, อำเภอ, สังกัดที่กล่าวถึงใหม่
2. ระบุ "current_focus" = โรงเรียน/จังหวัดที่ผู้ใช้กำลังถามถึง
3. ถ้าไม่มีข้อมูลใหม่ให้ตอบ empty arrays

**ตอบเป็น JSON เท่านั้น (ไม่ต้องมี markdown):**
{{"new_schools": ["..."], "new_provinces": ["..."], "new_districts": ["..."], "new_agencies": ["..."], "current_school": "...", "current_province": "...", "topic": "..."}}
"""
        
        try:
            response = self.llm.generate_content(prompt, timeout=5)
            if response and response.text:
                # Parse JSON from response
                extracted = self._parse_json_response(response.text)
                
                if extracted:
                    # Update context with new entities
                    for school in extracted.get("new_schools", []):
                        existing_context.add_entity("schools", school)
                    for province in extracted.get("new_provinces", []):
                        existing_context.add_entity("provinces", province)
                    for district in extracted.get("new_districts", []):
                        existing_context.add_entity("districts", district)
                    for agency in extracted.get("new_agencies", []):
                        existing_context.add_entity("agencies", agency)
                    
                    # Update current focus
                    if extracted.get("current_school"):
                        existing_context.current_school = extracted["current_school"]
                    if extracted.get("current_province"):
                        existing_context.current_province = extracted["current_province"]
                    if extracted.get("topic"):
                        existing_context.current_topic = extracted["topic"]
                    
                    logger.info(f"🧠 LLM Context Extracted: schools={existing_context.schools}, provinces={existing_context.provinces}")
                    
        except Exception as e:
            logger.warning(f"⚠️ LLM context extraction failed: {e}")
            # Fallback: Use simple rule-based extraction
            self._fallback_extraction(query, existing_context)
        
        return existing_context
    
    def resolve_coreferences(self, query: str, context: SessionContext, history: List[Dict] = None) -> str:
        """
        Phase 3: Resolve pronouns/references to actual entities
        
        Examples:
            "มีนักเรียนกี่คน?" + context.current_school="สวนกุหลาบ"
            → "โรงเรียนสวนกุหลาบมีนักเรียนกี่คน?"
        """
        # Check if query contains pronouns or references
        pronoun_patterns = ["มัน", "เขา", "ที่นั่น", "โรงเรียนนั้น", "โรงเรียนนี้", "จังหวัดนั้น",
                           "มีกี่คน", "มีเท่าไหร่", "แล้ว", "ล่ะ"]
        
        needs_resolution = any(p in query for p in pronoun_patterns)
        
        if not needs_resolution:
            return query  # No resolution needed
        
        # 🆕 TRY RULE-BASED FIRST for follow-up patterns like "แล้วXละ"
        # Rule-based is more reliable for these specific patterns
        if "แล้ว" in query:
            rule_resolved = self._rule_based_coreference(query, context, history or [])
            if rule_resolved != query:
                logger.info(f"🔧 Rule-based priority: '{query}' → '{rule_resolved}'")
                return rule_resolved
        
        # Need context for LLM resolution
        if not context.schools and not context.provinces:
            return query
        
        prompt = f"""แปลงคำถามให้ชัดเจนโดยใส่ชื่อจริงแทน "มัน/เขา/ที่นั่น"

**คำถาม:** "{query}"

**Entities ที่รู้จัก:**
- โรงเรียนล่าสุด: {context.schools[-2:] if context.schools else ["ไม่มี"]}
- จังหวัดล่าสุด: {context.provinces[-2:] if context.provinces else ["ไม่มี"]}
- โรงเรียนที่กำลังถาม: {context.current_school or "ไม่ระบุ"}
- จังหวัดที่กำลังถาม: {context.current_province or "ไม่ระบุ"}

**คำสั่ง:**
- ถ้าคำถามคลุมเครือ (เช่น "มีกี่คน?" "แล้วครูล่ะ?") → ใส่ชื่อโรงเรียน/จังหวัดให้ชัดเจน
- ถ้าคำถามชัดเจนอยู่แล้ว → ตอบเหมือนเดิม
- ตอบแค่คำถามใหม่ ไม่ต้องอธิบาย
"""
        
        try:
            response = self.llm.generate_content(prompt, timeout=5)
            if response and response.text:
                resolved = response.text.strip().strip('"').strip("'")
                if resolved and len(resolved) > 5:  # Sanity check
                    logger.info(f"🔄 Coreference: '{query}' → '{resolved}'")
                    return resolved
        except Exception as e:
            logger.warning(f"⚠️ Coreference resolution failed: {e}")
        
        # Final fallback to rule-based
        return self._rule_based_coreference(query, context, history or [])

    
    def summarize_memory(self, history: List[Dict], context: SessionContext) -> Optional[str]:
        """
        Phase 4: Summarize old conversation into long-term memory
        
        Called when history gets too long (>15 messages)
        """
        if len(history) < 15:
            return None  # No summarization needed
        
        # Summarize the older messages (not recent 5)
        old_messages = history[:-5]
        old_history_text = self._format_history(old_messages)
        
        prompt = f"""สรุปบทสนทนาต่อไปนี้เป็น 2-3 ประโยคสั้นๆ:

{old_history_text}

**เน้นสรุป:**
- โรงเรียน/จังหวัดที่ผู้ใช้สนใจ
- ข้อมูลที่ผู้ใช้ถามหา
- ประเด็นสำคัญที่คุยกัน

**ตอบเป็นสรุปสั้นๆ:**
"""
        
        try:
            response = self.llm.generate_content(prompt, timeout=8)
            if response and response.text:
                summary = response.text.strip()
                context.long_term_summary = summary
                logger.info(f"📝 Memory summarized: {summary[:100]}...")
                return summary
        except Exception as e:
            logger.warning(f"⚠️ Memory summarization failed: {e}")
        
        return None
    
    def get_context_for_query(self, query: str, history: List[Dict], 
                               session_id: str) -> Dict[str, Any]:
        """
        Main entry point: Get full context for a query
        
        Returns dict with:
            - resolved_query: Query with coreferences resolved
            - context: SessionContext object
            - context_summary: String summary for LLM prompt
        """
        # Get or create context
        context = self.get_or_create_context(session_id)
        
        # Phase 1: Extract context with LLM
        context = self.extract_context_with_llm(query, history, context)
        
        # Phase 3: Resolve coreferences (pass history for topic extraction)
        resolved_query = self.resolve_coreferences(query, context, history)
        
        # Phase 4: Summarize if needed
        if len(history) >= 15 and not context.long_term_summary:
            self.summarize_memory(history, context)
        
        # Build context summary for LLM prompt
        context_summary = self._build_context_summary(context)
        
        # 🆕 Save context to Redis after modifications
        self.save_context(session_id, context)
        
        return {
            "resolved_query": resolved_query,
            "context": context,
            "context_summary": context_summary
        }
    
    def _format_history(self, history: List[Dict]) -> str:
        """Format history for LLM prompt"""
        lines = []
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")[:200]  # Truncate long messages
            lines.append(f"{role}: {content}")
        return "\n".join(lines)
    
    def _parse_json_response(self, text: str) -> Optional[Dict]:
        """Parse JSON from LLM response (handles markdown blocks)"""
        # Clean up response
        text = text.strip()
        
        # Remove markdown code blocks if present
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        
        text = text.strip()
        
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON object in text
            import re
            match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass
            return None
    
    def _build_context_summary(self, context: SessionContext) -> str:
        """Build human-readable context summary"""
        parts = []
        
        if context.current_school:
            parts.append(f"- โรงเรียนที่ถาม: {context.current_school}")
        if context.current_province:
            parts.append(f"- จังหวัด: {context.current_province}")
        if context.schools and len(context.schools) > 1:
            parts.append(f"- โรงเรียนที่กล่าวถึง: {', '.join(context.schools[-3:])}")
        if context.long_term_summary:
            parts.append(f"- สรุปบทสนทนา: {context.long_term_summary}")
        
        return "\n".join(parts) if parts else ""
    
    def _fallback_extraction(self, query: str, context: SessionContext):
        """Simple rule-based fallback when LLM fails"""
        # Basic province detection
        provinces = ["กรุงเทพ", "เชียงใหม่", "เชียงราย", "นราธิวาส", "ปัตตานี", "ยะลา",
                    "ภูเก็ต", "ขอนแก่น", "นครราชสีมา", "อุดรธานี", "สงขลา"]
        for prov in provinces:
            if prov in query:
                context.add_entity("provinces", prov)
                context.current_province = prov
                break
        
        # Basic school name detection
        if "โรงเรียน" in query:
            import re
            match = re.search(r'โรงเรียน(\S+)', query)
            if match:
                school_name = match.group(1)
                context.add_entity("schools", school_name)
                context.current_school = school_name

    def _rule_based_coreference(self, query: str, context: SessionContext, history: List[Dict] = None) -> str:
        """
        Rule-based fallback for coreference resolution when LLM is unavailable.
        Handles common Thai follow-up patterns.
        Now extracts topic from conversation history.
        """
        import re
        history = history or []
        
        # 🆕 Extract topic from previous USER messages in history
        topic = None
        for msg in reversed(history):
            if msg.get("role") == "user":
                prev_query = msg.get("content", "")
                # Detect topic from previous question
                if "โรงเรียน" in prev_query or "กี่แห่ง" in prev_query:
                    topic = "schools"
                    break
                elif "ครู" in prev_query or "อาจารย์" in prev_query or "บุคลากร" in prev_query:
                    topic = "teachers"
                    break
                elif "นักเรียน" in prev_query or "เด็ก" in prev_query:
                    topic = "students"
                    break
        
        # Fallback to context.current_topic if history parsing failed
        if not topic and context.current_topic:
            if "โรงเรียน" in context.current_topic or "school" in context.current_topic.lower():
                topic = "schools"
            elif "ครู" in context.current_topic or "teacher" in context.current_topic.lower():
                topic = "teachers"
            elif "นักเรียน" in context.current_topic or "student" in context.current_topic.lower():
                topic = "students"
        
        # Default topic
        if not topic:
            topic = "schools"  # Most common query type
        
        logger.info(f"🔧 Rule-based: Extracted topic='{topic}' from history")
        
        # Regions for detection
        REGIONS = ["ภาคเหนือ", "ภาคใต้", "ภาคตะวันออก", "ภาคตะวันตก", "ภาคกลาง", 
                   "ภาคตะวันออกเฉียงเหนือ", "ภาคอีสาน"]
        
        # Pattern 0: "แล้วปี XX" or "ปี 67 ละ" — year-change follow-up
        # Reconstructs previous query with new year, preserving province/topic context
        year_change_match = re.search(r'(?:แล้ว)?ปี(?:การศึกษา)?\s*(\d{2,4})(?:\s*(?:ละ|ล่ะ|ล่ะครับ|ละครับ|หล่ะ))?', query)
        if year_change_match:
            year_str = year_change_match.group(1)
            # Check if this is primarily a year-change query (short query with just year info)
            query_without_year = re.sub(r'(?:แล้ว)?ปี(?:การศึกษา)?\s*\d{2,4}(?:\s*(?:ละ|ล่ะ|ล่ะครับ|ละครับ|หล่ะ))?', '', query).strip()
            is_year_only_query = len(query_without_year) < 10  # Very little besides the year
            
            if is_year_only_query:
                # This is a pure year-change follow-up → reconstruct from history + topic
                province_str = ""
                if context.current_province:
                    province_str = context.current_province
                elif context.provinces:
                    province_str = context.provinces[-1]
                
                # Fallback: extract province from conversation history
                if not province_str:
                    from ..core.constants import THAI_PROVINCES
                    for msg in reversed(history):
                        if msg.get("role") == "user":
                            prev_text = msg.get("content", "")
                            for prov in THAI_PROVINCES:
                                if prov in prev_text:
                                    province_str = prov
                                    break
                            # Also check for regions
                            if not province_str:
                                for region in REGIONS:
                                    if region in prev_text:
                                        province_str = region
                                        break
                            if province_str:
                                break
                
                # Build resolved query based on topic
                if topic == "schools":
                    subject, unit = "โรงเรียน", "กี่แห่ง"
                elif topic == "teachers":
                    subject, unit = "ครู", "กี่คน"
                elif topic == "students":
                    subject, unit = "นักเรียน", "กี่คน"
                else:
                    subject, unit = "โรงเรียน", "กี่แห่ง"
                
                if province_str:
                    resolved = f"{province_str}ปี {year_str} มี{subject}{unit}"
                else:
                    resolved = f"ปี {year_str} มี{subject}{unit}"
                
                logger.info(f"📅 Year-change coreference: '{query}' → '{resolved}' (topic={topic})")
                return resolved
        
        # Pattern 1: "แล้วXละ" or "แล้วXล่ะ" - follow-up with new entity
        followup_match = re.search(r'แล้ว(.+?)(?:ละ|ล่ะ|ล่ะครับ|ละครับ)?$', query)
        if followup_match:
            entity = followup_match.group(1).strip()
            
            # 🆕 Active Query Substitution (Phase 5)
            # Use exact tool capability from previous turn to reconstruct query
            if context.last_active_query:
                try:
                    last_tool = context.last_active_query.get("name")
                    # last_params = context.last_active_query.get("params", {}) # Not used yet for simple reconstruction
                    
                    # Detect entity type
                    is_region = any(region in entity for region in REGIONS)
                    from ..core.constants import THAI_PROVINCES
                    is_province = any(prov in entity for prov in THAI_PROVINCES)
                    
                    if is_region or is_province:
                        # Handle Count Tools
                        tool_map = {
                            "count_schools": "โรงเรียน",
                            "count_teachers": "ครู",
                            "count_students": "นักเรียน",
                            "get_ratio": "อัตราส่วนครูต่อนักเรียน"
                        }
                        
                        if last_tool in tool_map:
                            subject = tool_map[last_tool]
                            unit = "แห่ง" if subject == "โรงเรียน" else "คน"
                            if last_tool == "get_ratio":
                                resolved = f"{subject}ใน{entity}เป็นเท่าไหร่"
                            else:
                                resolved = f"{entity}มี{subject}กี่{unit}"
                                
                            logger.info(f"🧠 Active Query Substitution: Tool='{last_tool}' -> '{resolved}'")
                            return resolved

                except Exception as e:
                    logger.warning(f"⚠️ Active Query Substitution failed: {e}")

            # Fallback to Topic-based Logic (Legacy Phase 3)
            # Detect if entity is a region
            
            # Detect if entity is a region
            for region in REGIONS:
                if region in entity:
                    # Use extracted topic
                    if topic == "schools":
                        resolved = f"{region}มีโรงเรียนกี่แห่ง"
                    elif topic == "teachers":
                        resolved = f"{region}มีครูกี่คน"
                    elif topic == "students":
                        resolved = f"{region}มีนักเรียนกี่คน"
                    else:
                        resolved = f"{region}มีโรงเรียนกี่แห่ง"
                    
                    logger.info(f"🔧 Rule-based: '{query}' → '{resolved}' (topic={topic})")
                    return resolved
            
            # If it's a province
            from ..core.constants import THAI_PROVINCES
            for prov in THAI_PROVINCES:
                if prov in entity:
                    if topic == "schools":
                        resolved = f"{prov}มีโรงเรียนกี่แห่ง"
                    elif topic == "teachers":
                        resolved = f"{prov}มีครูกี่คน"
                    elif topic == "students":
                        resolved = f"{prov}มีนักเรียนกี่คน"
                    else:
                        resolved = f"{prov}มีโรงเรียนกี่แห่ง"
                    
                    logger.info(f"🔧 Rule-based: '{query}' → '{resolved}' (province, topic={topic})")
                    return resolved
        
        # Pattern 2: Short question like "มีกี่คน?" with no subject
        if len(query) < 15 and ("มีกี่คน" in query or "มีกี่แห่ง" in query or "เท่าไหร่" in query):
            if context.current_school:
                resolved = f"โรงเรียน{context.current_school}{query}"
                logger.info(f"🔧 Rule-based: '{query}' → '{resolved}' (school context)")
                return resolved
            elif context.current_province:
                resolved = f"{context.current_province}{query}"
                logger.info(f"🔧 Rule-based: '{query}' → '{resolved}' (province context)")
                return resolved
        
        # No resolution possible
        return query
