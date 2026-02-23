"""
Education Chatbot Core
Main EducationChatbot class that orchestrates all components

📄 ชื่อไฟล์: chatbot_core.py  
📝 คำอธิบาย:
   หัวใจหลักของระบบ Chatbot (Core Logic)
   ทำหน้าที่ควบคุมการทำงานของ AI และการค้นหาข้อมูลทั้งหมด

🛠 หน้าที่หลัก:
   1. Intent Classification: วิเคราะห์เจตนาของผู้ใช้ (ถามทั่วไป vs ถามข้อมูลการศึกษา)
   2. Search Orchestration: สั่งค้นหาข้อมูลด้วย SearchEngine และ Qdrant
   3. RAG System: นำข้อมูลที่ได้มาประกอบ Prompt ส่งให้ AI ตอบ
   4. Response Synthesizer: เรียบเรียงคำตอบให้อยู่ในรูปแบบที่สวยงาม (ตาราง, อันดับ, กราฟ)

📂 โครงสร้างโค้ด (Code Organization):
   ├─ INITIALIZATION (line ~60-110)      : __init__, _init_model, _get_collections
   ├─ MAIN CHAT (line ~110-530)          : chat() main entry point  
   ├─ SCHOOL HANDLERS (line ~530-1220)   : school queries, count, list, search
   └─ SEARCH & AGGREGATE (line ~1220-1380): execute search, aggregate results 
   
   📦 EXTRACTED TO MIXINS:
   ├─ handlers/llm_handlers.py    : LLM methods (intent, RAG, formatting)
   └─ handlers/stats_handlers.py  : Stats handlers (student, teacher, ratio, ranking)
"""

import re
import os
import time
import logging
from typing import List, Dict, Generator, Tuple, Optional, Any

import google.generativeai as genai
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
import json

from .core.types import (
    QueryIntent, QueryLevel, ParsedQuery, SearchResult
)
from .core.constants import COLLECTION_NAMES
from .core.constants import COLLECTIONS, REGIONS, THAI_PROVINCES, PROVINCE_ALIASES
from .core.security import input_sanitizer
from .core.llm import MultiProviderLLM
from .data.cache import HybridCache
from .search.query_parser import SmartQueryParser, ResponseSynthesizer
from .search.search_engine import SearchEngine
from .search.school_search import SchoolSearchEngine
from .data.aggregators import ResultAggregator
from .data.formatters import ResponseFormatter
from .data.memory import ConversationMemory
from .llm_agent import LLMAgent
from .data.context_manager import ContextManager

# Import handler mixins
from .handlers import (
    LLMHandlersMixin,
    StatsHandlersMixin,
    InterceptHandlersMixin,
    SchoolHandlersMixin,
    SearchHandlersMixin,
)

logger = logging.getLogger(__name__)

# Model configuration
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant')  # 8b has separate quota
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')


# =============================================================================
# INITIALIZATION SECTION
# =============================================================================

class EducationChatbot(
    InterceptHandlersMixin,   # disambiguation + year comparison interceptors
    SchoolHandlersMixin,      # school query/count/list/search handlers
    SearchHandlersMixin,      # search execution, cache, context
    LLMHandlersMixin,         # LLM intent/RAG
    StatsHandlersMixin,       # stats handlers
):
    """Production-ready Education Chatbot with mixin-based handlers"""


    def __init__(self, qdrant_client: QdrantClient, model_name: str = 'gemini-2.5-flash'):
        logger.info("🚀 Initializing Education Chatbot v5.0...")
        
        self.qdrant_client = qdrant_client
        
        # Initialize LLM First (needed for SearchEngine)
        self.model = self._init_model(model_name)
        
        # 1. Health Check & Collections Load (Fail Fast)
        self.collections = {}
        try:
            self.collections = self._get_collections()
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            
        self.qdrant_available = len(self.collections) > 0
        
        if not self.qdrant_available:
            logger.warning("⚠️ Qdrant is DOWN. Functionality limited to LLM-Only.")
            self.parser = None
            self.search_engine = None
            self.aggregator = None
            self.cache = None
        else:
            self.parser = SmartQueryParser(qdrant_client=qdrant_client)
            self.search_engine = SearchEngine(qdrant_client, parser=self.parser, llm_provider=self.model)
            self.aggregator = ResultAggregator()
            self.cache = HybridCache(qdrant_client, llm_provider=self.model)
            
        self.memory = ConversationMemory()
        # self.model initialized above
        self.formatter = ResponseFormatter(model=self.model, model_name=model_name)
        # self.collections already loaded
        
        # 🆕 Initialize LLM Agent for Function Calling
        self._init_llm_agent()
        
        # 🆕 Initialize Advanced Context Manager (LLM-based with Redis storage)
        redis_client = self.cache.redis_client if self.cache else None
        self.context_manager = ContextManager(self.model, redis_client=redis_client)
        
        # Self-Healing: Track last check time
        import time
        self.last_qdrant_check = time.time()
        
        logger.info(f"✅ Chatbot ready with {len(self.collections)} collections (LLM Agent enabled)")
    
    def _try_reconnect_qdrant(self):
        """🔄 Attempt to reconnect to Qdrant if previously unavailable"""
        import time
        try:
            logger.info("🔄 Attempting to reconnect to Qdrant...")
            self.collections = self._get_collections()
            
            if len(self.collections) > 0:
                logger.info("🎉 Qdrant is back ONLINE! Re-initializing components...")
                self.parser = SmartQueryParser(qdrant_client=self.qdrant_client)
                self.search_engine = SearchEngine(self.qdrant_client, parser=self.parser, llm_provider=self.model)
                self.aggregator = ResultAggregator()
                self.cache = HybridCache(self.qdrant_client, llm_provider=self.model)
                
                # Re-init LLM Agent with DB access
                self._init_llm_agent()
                
                self.qdrant_available = True
                logger.info("✅ System fully recovered!")
                return True
            else:
                logger.warning("⚠️ Reconnect failed: No collections found")
                
        except Exception as e:
            logger.warning(f"⚠️ Reconnect failed: {e}")
            
        self.last_qdrant_check = time.time()
        return False

    def _init_model(self, model_name: str):
        """Initialize LLM with Groq → Gemini fallback"""
        try:
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
            all_collections = self.qdrant_client.get_collections()
            for level, name in COLLECTIONS.items():
                if any(c.name == name for c in all_collections.collections):
                    available[level] = name
                    logger.info(f"   ✅ {level}: {name}")
        except Exception as e:
            logger.error(f"Failed to get collections: {e}")
        return available
    
    def _init_llm_agent(self):
        """🆕 Initialize LLM Agent for intelligent tool calling"""
        try:
            self.llm_agent = LLMAgent(self.qdrant_client, self.model)
            self.use_llm_agent = True
            logger.info("✅ LLM Agent initialized (Function Calling enabled)")
        except Exception as e:
            logger.warning(f"⚠️ LLM Agent init failed: {e}. Using legacy handlers.")
            self.llm_agent = None
            self.use_llm_agent = False
    
    def process_with_llm_agent(self, message: str, rich_context: Dict = None, session_context=None, session_id=None) -> Optional[str]:
        """
        🆕 Process query using LLM Agent (Function Calling approach)
        Returns response string or None if agent is not available
        """
        if not self.use_llm_agent or not self.llm_agent:
            return None
            
        try:
            # Pass memory as context (Prefer rich context if available)
            context = rich_context if rich_context else (self.memory.to_dict() if self.memory else {})
            
            # Unpack tuple from process_query (response, active_query)
            response, active_query = self.llm_agent.process_query(message, context=context)
            
            # 💾 Save Active Query to Session Context
            if active_query and session_context and session_id and self.context_manager:
                session_context.last_active_query = active_query
                self.context_manager.save_context(session_id, session_context)
                logger.info(f"💾 Active Query Saved: {active_query.get('name')} (Session: {session_id})")

            # Fallback storage in in-process memory (covers sessions where ContextManager is bypassed)
            if active_query and self.memory is not None:
                self.memory.last_active_query = active_query

            # 🧠 UPDATE MEMORY: Extract entities from active_query and persist for follow-up
            if active_query and self.memory:
                params = active_query.get('params', {})
                if params.get('province'):
                    self.memory.last_province = params['province']
                    logger.info(f"🧠 Memory updated: province={params['province']}")
                if params.get('region'):
                    self.memory.last_region = params['region']
                    logger.info(f"🧠 Memory updated: region={params['region']}")
                if params.get('school_name'):
                    self.memory.last_school_name = params['school_name']
                    logger.info(f"🧠 Memory updated: school_name={params['school_name']}")
                if params.get('district'):
                    self.memory.last_district = params['district']
                if params.get('agency'):
                    self.memory.last_agency = params['agency']

                # Track scope + freshness for smarter context
                scope_type = None
                scope_value = None
                if params.get('school_name'):
                    scope_type = "school"
                    scope_value = params.get('school_name')
                elif params.get('district'):
                    scope_type = "district"
                    scope_value = params.get('district')
                elif params.get('province'):
                    scope_type = "province"
                    scope_value = params.get('province')
                elif params.get('region'):
                    scope_type = "region"
                    scope_value = params.get('region')

                if scope_type and self.memory:
                    self.memory.last_scope_type = scope_type
                    self.memory.last_scope_value = scope_value
                    try:
                        import time
                        self.memory.last_updated_at = time.time()
                    except Exception:
                        pass
            
            return response
        except Exception as e:
            logger.error(f"❌ LLM Agent processing failed: {e}")
            return None






    # =========================================================================
    # MAIN CHAT INTERFACE: Entry point for all conversations
    # =========================================================================

    def chat(self, message: str, history: List[Dict[str, str]] = None, session_id: Optional[str] = None) -> Generator[Tuple[List[Dict[str, str]], str], None, None]:
        """Main chat interface"""
        if history is None:
            history = []
            
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": ""})
        
        # Input Sanitization
        sanitized_message, error = input_sanitizer.sanitize(message)
        if error:
            history[-1]["content"] = error
            yield history, ""
            return
        message = sanitized_message
        
        # Check reset command
        if message.lower() in ['reset', 'clear', 'ล้าง', 'เริ่มใหม่']:
            self.memory.clear()
            history[-1]["content"] = "ล้างความจำเรียบร้อยครับ เริ่มต้นใหม่ได้เลย! ✨"
            yield history, ""
            return
        
        logger.info(f"💬 User: {message}")
        
        # 🆕 INTERCEPTOR: Disambiguation selection (e.g., user sends "1" to pick a school)
        # Must run BEFORE parser to prevent early LLM Agent fallback on unparseable "1"
        past_history_for_disambig = history[:-2] if len(history) > 2 else []
        disambig_result = self._try_disambiguation_intercept(message, past_history_for_disambig)
        if disambig_result:
            history[-1]["content"] = disambig_result
            yield history, ""
            return

        # 🧠 HYBRID CONTEXT MANAGEMENT
        # Use LLM ContextManager ONLY when needed (ambiguous follow-ups)
        ctx = None
        past_history = history[:-2] if len(history) > 2 else []  # Exclude current exchange
        session_key = str(session_id) if session_id else str(hash(str(history[:2])) if history else "default")

        was_coreference_resolved = False
        if self.context_manager and self._should_use_llm_context(message, past_history):
            try:
                context_result = self.context_manager.get_context_for_query(
                    query=message,
                    history=past_history,
                    session_id=session_key
                )

                # Use resolved query (with coreferences replaced)
                resolved_message = context_result.get("resolved_query", message)
                was_coreference_resolved = False
                if resolved_message != message:
                    logger.info(f"🔄 Query resolved: '{message}' → '{resolved_message}'")
                    message = resolved_message
                    was_coreference_resolved = True

                # Update legacy memory for backward compatibility
                ctx = context_result.get("context")
                if ctx:
                    if ctx.current_school:
                        self.memory.last_school_name = ctx.current_school
                    if ctx.current_province:
                        self.memory.last_province = ctx.current_province
                    logger.info(f"🧠 Context: schools={ctx.schools[-3:]}, provinces={ctx.provinces[-3:]}, focus={ctx.current_school or ctx.current_province}")
            except Exception as e:
                logger.warning(f"⚠️ Context extraction failed, using fallback: {e}")
                # Fallback to old rule-based extraction
                if history and len(history) >= 4:
                    last_ai_response = history[-3].get("content", "")
                    school_match = re.search(r'(?:โรงเรียน|วิทยาลัย)(\s*[ก-๙a-zA-Z0-9]+(?:[ \t][ก-๙a-zA-Z0-9]+)*)', last_ai_response)
                    if school_match:
                        extracted_name = school_match.group(1).strip()
                        if len(extracted_name) > 3 and not any(x in extracted_name for x in ['คือ', 'มี', 'อยู่', 'เป็น']):
                            self.memory.last_school_name = extracted_name
                            logger.info(f"🧠 Context Restored (fallback): {extracted_name}")
        
        # ⚠️ CRITICAL FALLBACK & SELF-HEALING
        if not self.qdrant_available:
            # 🔄 Lazy Retry: Check Qdrant every 60 seconds
            import time
            if time.time() - self.last_qdrant_check > 60:
                self._try_reconnect_qdrant()
                
            if not self.qdrant_available:
                logger.warning("🚨 Qdrant is unavailable. Using LLM-Only Fallback.")
                try:
                    # Use general response generator (wrapper around LLM)
                    response = self._generate_general_response(message)
                    if response:
                        history[-1]["content"] = response + "\n\n(⚠️ ระบบฐานข้อมูลกำลังปิดปรับปรุง ตอบได้เฉพาะข้อมูลทั่วไปครับ)"
                        yield history, ""
                        return
                    else:
                        history[-1]["content"] = "ขออภัยครับ ระบบฐานข้อมูลไม่พร้อมใช้งานในขณะนี้ 🙏"
                        yield history, ""
                        return
                except Exception as e:
                    logger.error(f"Fallback LLM failed: {e}")
                    history[-1]["content"] = "ขออภัยครับ ระบบกำลังขัดข้อง (Database & LLM Unreachable)"
                    yield history, ""
                    return

        # ⚠️ Cache toggle via env (default: enabled)
        enable_cache = os.getenv("ENABLE_SEMANTIC_CACHE", "1") == "1"
        DEBUG_DISABLE_CACHE = not enable_cache
        
        # Check if this is a school-specific query (bypass cache for fresh results)
        def _is_school_specific_message(msg: str, school_name: str) -> bool:
            if not msg or not school_name:
                return False
            msg_norm = msg.replace(" ", "")
            school_norm = school_name.replace("โรงเรียน", "").replace(" ", "")
            if school_norm and school_norm in msg_norm:
                return True
            school_keywords = ["โรงเรียน", "วิทยาลัย", "สถาบัน", "มหาวิทยาลัย"]
            return any(k in msg for k in school_keywords)

        is_school_specific_query = False
        if hasattr(self.memory, 'last_school_name') and self.memory.last_school_name:
            is_school_specific_query = _is_school_specific_message(message, self.memory.last_school_name)

        def _is_short_followup_message(msg: str) -> bool:
            if not msg:
                return False
            m = msg.strip()
            follow_kws = [
                "แล้ว", "ล่ะ", "ละ", "ต่อ", "อีก", "เพิ่ม", "สรุปอีกที",
                "เท่าไหร่", "กี่คน", "กี่แห่ง", "มากกว่า", "น้อยกว่า"
            ]
            return len(m) <= 60 and any(k in m for k in follow_kws)

        def _is_subjective_best_school_query(msg: str) -> bool:
            if not msg:
                return False
            m = msg.strip()
            m_norm = m.replace(" ", "")
            has_school = "โรงเรียน" in m
            has_best = any(k in m_norm for k in ["โรงเรียนไหนดี", "ไหนดีสุด", "ดีที่สุด"])
            has_metric_or_scope = any(
                k in m for k in [
                    "อัตราส่วน", "นักเรียน", "ครู", "ผลสอบ", "คะแนน", "ใกล้",
                    "สังกัด", "ค่าเทอม", "จังหวัด", "อำเภอ", "ภาค", "อันดับ"
                ]
            )
            return has_school and has_best and not has_metric_or_scope

        if is_school_specific_query:
            logger.info(f"🏫 School-specific query detected (school_name: {self.memory.last_school_name}) - skipping cache")
        is_short_followup_query = _is_short_followup_message(message)
        if is_short_followup_query:
            logger.info("🔄 Short follow-up query detected - skipping cache for context-safe routing")
        is_subjective_best_query = _is_subjective_best_school_query(message)
        if is_subjective_best_query:
            logger.info("🧭 Subjective best-school query detected - skipping cache to force ask-back clarification")
        
        # Cache context = evaluate using current message + memory
        def _cache_ctx() -> Optional[Dict[str, str]]:
            return self._get_cache_context(message)
        
        # Check Semantic Cache (disabled for testing)
        if DEBUG_DISABLE_CACHE:
            logger.info("🔧 Cache DISABLED by env (ENABLE_SEMANTIC_CACHE=0)")
        elif (
            not is_school_specific_query
            and not is_short_followup_query
            and not is_subjective_best_query
            and self.cache
            and not was_coreference_resolved
        ):
            cached_response = self.cache.check(message, context=_cache_ctx())
            if cached_response:
                # CRITICAL: Still update memory on cache hit so follow-up queries retain context
                try:
                    cache_parsed = self.parser.parse(message)
                    if cache_parsed:
                        self.memory.update(cache_parsed, original_query=message)
                        inferred_active_query = self._infer_active_query_from_parsed(cache_parsed, message)
                        if inferred_active_query:
                            self.memory.last_active_query = inferred_active_query
                            logger.info(f"💾 Active Query inferred (cache hit): {inferred_active_query.get('name')}")
                        logger.info(f"🧠 Memory updated (cache hit): province={cache_parsed.province}, year={self.memory.last_year}")
                    else:
                        # Even if parser fails, extract year from the message
                        self.memory.update(self.parser.parse("") or ParsedQuery(intent=QueryIntent.COUNT), original_query=message)
                except Exception as e:
                    logger.warning(f"⚠️ Memory update on cache hit failed: {e}")
                history[-1]["content"] = cached_response
                yield history, ""
                return

        # Parse query intent
        parsed = self.parser.parse(message)
        if not parsed:
            logger.warning("⚠️ Parser returned None - trying LLM Agent fallback")
            # Try LLM Agent for difficult queries (follow-ups, ambiguous queries)
            if self.use_llm_agent and self.llm_agent:
                try:
                    context = self.memory.to_dict() if self.memory else {}
                    llm_response, _ = self.llm_agent.process_query(message, context=context)
                    if llm_response and "ไม่สามารถ" not in llm_response:
                        history[-1]["content"] = llm_response
                        yield history, ""
                        return
                except Exception as e:
                    logger.error(f"❌ LLM Agent fallback failed: {e}")
            
            # Final fallback
            logger.error("❌ Both parser and LLM Agent failed")
            history[-1]["content"] = "ขออภัยครับ ไม่สามารถเข้าใจคำถามได้ โปรดลองอีกครั้ง"
            yield history, ""
            return
            
        parsed = self.memory.apply_context(parsed, message)
        
        # NEW: Check if frontend injected a school_name via memory (only use when likely follow-up)
        if hasattr(self.memory, 'last_school_name') and self.memory.last_school_name:
            school_name = self.memory.last_school_name
            msg = message or ""
            msg_norm = msg.replace(" ", "")
            school_norm = school_name.replace("โรงเรียน", "").replace(" ", "")
            follow_kws = ["แล้ว", "ต่อ", "อีก", "เพิ่ม", "ขอรายละเอียด", "รายละเอียด", "พิกัด", "ที่ไหน", "เบอร์ติดต่อ", "ครูกี่", "นักเรียนกี่", "ข้อมูล"]
            is_followup = len(msg) <= 28 and any(k in msg for k in follow_kws)
            has_school_ref = school_norm and school_norm in msg_norm
            has_school_kw = any(k in msg for k in ["โรงเรียน", "วิทยาลัย", "สถาบัน", "มหาวิทยาลัย"])
            is_broad_scope = any(k in msg for k in ["จังหวัด", "อำเภอ", "ภาค", "อันดับ", "มากที่สุด", "น้อยที่สุด", "สรุป"])
            is_aggregate_intent = parsed.intent in [
                QueryIntent.COUNT,
                QueryIntent.RANKING_MOST,
                QueryIntent.RANKING_LEAST,
                QueryIntent.SCHOOL_COUNT,
                QueryIntent.STUDENT_COUNT,
                QueryIntent.TEACHER_COUNT,
                QueryIntent.LIST,
                QueryIntent.SCHOOL_LIST,
                QueryIntent.SEARCH,
                QueryIntent.SCHOOL_SEARCH,
                QueryIntent.FILTER_LESS_THAN,
                QueryIntent.FILTER_GREATER_THAN,
                QueryIntent.FILTER_EQUALS,
                QueryIntent.RATIO,
            ]

            if (has_school_ref or has_school_kw or is_followup) and not is_broad_scope and not is_aggregate_intent:
                logger.info(f"🏫 Using memory school_name for follow-up: {school_name}")
                parsed.intent = QueryIntent.SCHOOL_DETAIL
                parsed.school_name = school_name
            else:
                logger.info(f"🏫 Skipped memory school_name (not follow-up): {school_name}")
        
        # NEW: Override parsed.level with frontend-provided level for correct collection routing
        if hasattr(self.memory, 'frontend_level') and self.memory.frontend_level:
            # QueryLevel is already imported at module level (line 27)
            level_map = {
                'province': QueryLevel.PROVINCE,
                'district': QueryLevel.DISTRICT,
                'subdistrict': QueryLevel.SUBDISTRICT,
                'agency': QueryLevel.AGENCY,
                # Note: 'school' is not a valid QueryLevel - school queries use SCHOOL_DETAIL intent instead
            }
            if self.memory.frontend_level in level_map:
                old_level = parsed.level.value if hasattr(parsed.level, 'value') else parsed.level
                parsed.level = level_map[self.memory.frontend_level]
                logger.info(f"📊 Frontend overrode level: {old_level} → {self.memory.frontend_level}")
            self.memory.frontend_level = None  # Clear after use
        
        self.memory.update(parsed, original_query=message)
        
        logger.info(f"🎯 Intent: {parsed.intent.value}, Level: {parsed.level.value}")
        logger.info(f"   Region: {parsed.region}, Province: {parsed.province}, School: {getattr(parsed, 'school_name', None)}")
        
        # Check for general queries in non-general categories
        current_category = getattr(self, '_current_category', 'general')
        is_non_general_category = current_category in ['school', 'student']
        
        if is_non_general_category:
            intent_type = self._classify_intent_with_llm(message)

            # If parser already produced a concrete education intent, do not downgrade to GENERAL
            education_intents = {
                QueryIntent.SCHOOL_COUNT,
                QueryIntent.STUDENT_COUNT,
                QueryIntent.TEACHER_COUNT,
                QueryIntent.SCHOOL_LIST,
                QueryIntent.SCHOOL_DETAIL,
                QueryIntent.RANKING_MOST,
                QueryIntent.RANKING_LEAST,
                QueryIntent.FILTER_LESS_THAN,
                QueryIntent.FILTER_GREATER_THAN,
                QueryIntent.FILTER_EQUALS,
                QueryIntent.RATIO,
                QueryIntent.SEARCH,
                QueryIntent.LIST,
                QueryIntent.COMPARE,
            }

            follow_kws = ["แล้ว", "ต่อ", "อีก", "เพิ่ม", "ล่ะ", "ละ", "ครับ", "ไหม"]
            is_followup = len(message or "") <= 28 and any(k in (message or "") for k in follow_kws)
            has_context = any([
                getattr(self.memory, "last_province", None),
                getattr(self.memory, "last_district", None),
                getattr(self.memory, "last_school_name", None),
                getattr(self.memory, "last_agency", None),
            ])
            rank_filter_kws = ["มากที่สุด", "น้อยที่สุด", "อันดับ", "มากกว่า", "น้อยกว่า", "เท่ากับ", "ไม่เกิน", "อย่างน้อย"]
            has_rank_filter_intent = any(k in (message or "") for k in rank_filter_kws)
            has_number = bool(re.search(r"\d", message or ""))

            if (
                parsed.intent in education_intents
                or (parsed.threshold is not None)
                or (has_rank_filter_intent and (has_context or has_number))
                or (is_followup and has_context)
            ):
                intent_type = "EDUCATION"

            logger.info(f"🧠 LLM Classified Intent: {intent_type}")
            
            EDUCATION_KEYWORDS = ['โรงเรียน', 'นักเรียน', 'ครู', 'การศึกษา', 'สพฐ', 'สช']
            has_strong_edu_keyword = any(kw in message for kw in EDUCATION_KEYWORDS)
            has_active_query_context = bool(getattr(self.memory, "last_active_query", None))
            has_followup_signal = any(k in (message or "") for k in ["แล้ว", "ล่ะ", "ละ", "ต่อ", "เพิ่ม", "อีก"])
            
            if (
                "GENERAL" in intent_type
                and not has_strong_edu_keyword
                and not has_rank_filter_intent
                and not (is_followup and has_context)
                and not has_active_query_context
                and not has_followup_signal
            ):
                # UNIFIED MODE: Respond directly with LLM for general/casual queries
                logger.info(f"🌐 General intent detected - responding with LLM directly")
                try:
                    general_response = self._generate_general_response(message)
                    if general_response:
                        history[-1]["content"] = general_response
                        self.cache.save(message, general_response, context=_cache_ctx())
                        yield history, ""
                        return
                except Exception as e:
                    logger.warning(f"⚠️ General LLM response failed: {e}")
                # Fall through to LLM Agent if general response fails

        # 🆕 INTERCEPTOR: Year comparison queries → direct tool call (bypass LLM)
        year_compare_result = self._try_year_comparison_intercept(message)
        if year_compare_result:
            history[-1]["content"] = year_compare_result
            self.cache.save(message, year_compare_result, context=_cache_ctx())
            yield history, ""
            return

        # 🆕 PRIMARY: Try LLM Agent (Function Calling approach) FIRST
        # This provides comprehensive query understanding without hardcoded handlers
        if self.use_llm_agent:
            logger.info("🤖 Using LLM Agent for query processing...")
            
            # Prepare rich context - merge SessionContext + Memory for complete context
            rich_context_dict = ctx.to_dict() if ctx else {}
            
            # 🔍 CRITICAL: Inject Last AI Response for Ambiguity Handling
            # usage: history = [..., {role: assistant, content: "Select school..."}, {role: user, content: "This one"}]
            if history and len(history) >= 3:
                last_msg = history[-3]
                if last_msg.get('role') == 'assistant':
                    rich_context_dict['last_ai_response'] = last_msg.get('content', '')
                    logger.info(f"🔍 Injected Last AI Response: {rich_context_dict['last_ai_response'][:50]}...")
            
            # 🔧 CRITICAL: Merge memory data for follow-up context
            if self.memory:
                def _should_ignore_school_context(msg: str, last_school: Optional[str]) -> bool:
                    if not msg or not last_school:
                        return False
                    msg_norm = msg.replace(" ", "")
                    school_norm = last_school.replace("โรงเรียน", "").replace(" ", "")
                    if school_norm and school_norm in msg_norm:
                        return False
                    agg_kws = [
                        "จังหวัด", "ภาค", "อำเภอ", "เขต", "ตำบล", "แขวง",
                        "อันดับ", "มากที่สุด", "น้อยที่สุด", "สูงสุด", "ต่ำสุด",
                        "สรุป", "รวม", "ทั้งหมด", "ทั่วประเทศ"
                    ]
                    return any(k in msg for k in agg_kws)

                ignore_school_context = _should_ignore_school_context(message, self.memory.last_school_name)

                if self.memory.last_province:
                    rich_context_dict['last_province'] = self.memory.last_province
                if self.memory.last_region:
                    rich_context_dict['last_region'] = self.memory.last_region
                if self.memory.last_school_name and not ignore_school_context:
                    rich_context_dict['last_school_name'] = self.memory.last_school_name
                if self.memory.last_district:
                    rich_context_dict['last_district'] = self.memory.last_district
                if self.memory.last_agency:
                    rich_context_dict['last_agency'] = self.memory.last_agency
                if self.memory.last_scope_type and not (ignore_school_context and self.memory.last_scope_type == "school"):
                    rich_context_dict['last_scope_type'] = self.memory.last_scope_type
                if self.memory.last_scope_value:
                    rich_context_dict['last_scope_value'] = self.memory.last_scope_value
                if getattr(self.memory, "last_active_query", None):
                    rich_context_dict['last_active_query'] = self.memory.last_active_query


            agent_response = self.process_with_llm_agent(
                message, 
                rich_context=rich_context_dict, 
                session_context=ctx, 
                session_id=session_key
            )
            
            if agent_response:
                history[-1]["content"] = agent_response
                self.cache.save(message, agent_response, context=_cache_ctx())
                yield history, ""
                return
            else:
                logger.info("⚠️ LLM Agent returned no response, falling back to legacy handlers")

        # ============================================================
        # LEGACY HANDLERS (DISABLED - Enforcing LLM Agent Flow)
        # ============================================================
        """
        # 🆕 Handle Ratio Queries FIRST (อัตราส่วนครู/นักเรียน) - most specific
        ratio_result = self._handle_ratio_query(parsed, message)
        if ratio_result:
            history[-1]["content"] = ratio_result
            self.cache.save(message, ratio_result, context=_cache_ctx())
            yield history, ""
            return

        # 🆕 Handle Teacher Count Queries FIRST (ครู, อาจารย์) - takes priority over student
        teacher_result = self._handle_teacher_count_query(parsed, message)
        if teacher_result:
            history[-1]["content"] = teacher_result
            self.cache.save(message, teacher_result, context=_cache_ctx())
            yield history, ""
            return

        # ... (Legacy handlers hidden) ...
        """

        # Handle School Queries (general - fallback)
        is_school_query = parsed.intent in [
            QueryIntent.SCHOOL_SEARCH, QueryIntent.SCHOOL_LIST, 
            QueryIntent.SCHOOL_DETAIL, QueryIntent.SCHOOL_COUNT
        ]
        
        if is_school_query:
            response_text = self._handle_school_query(parsed, message, history)
            if response_text:
                history[-1]["content"] = response_text
                self.cache.save(message, response_text, context=_cache_ctx())
                yield history, ""
                return
        
        
        # Handle Load More
        if parsed.intent == QueryIntent.LOAD_MORE:
            response_text = self._handle_load_more()
            history[-1]["content"] = response_text
            yield history, ""
            return
        
        # Handle Ranking/Compare/Normal queries
        results = self._execute_search(parsed, message, history)
        if results is None:
            yield history, ""
            return
        
        # Aggregate results
        aggregated = self._aggregate_results(results, parsed, message)
        
        # Use ResponseSynthesizer for RANKING queries
        if parsed.intent in [QueryIntent.RANKING_MOST, QueryIntent.RANKING_LEAST]:
            synthesizer = ResponseSynthesizer()
            
            # Prepare data for synthesizer
            ranking_data = {
                "query_type": "ranking",
                "intent": parsed.intent.value,
                "location_level": parsed.level.value,
                "data": []
            }
            
            chart_data = [] # For <chart> widget
            
            num_items = min(10, len(aggregated.data))
            for i, (name, data) in enumerate(aggregated.data[:num_items], 1):
                # Format name for display
                display_name = name
                if '|' in name:
                    parts = name.split('|')
                    if parsed.level == QueryLevel.DISTRICT and len(parts) >= 2:
                        display_name = f"{parts[1]} ({parts[0]})"
                    elif parsed.level == QueryLevel.SUBDISTRICT and len(parts) >= 3:
                        display_name = f"{parts[2]} ({parts[1]})"
                
                ranking_data["data"].append({
                   "rank": i,
                   "name": display_name,
                   "count": data['total'],
                   "agencies": data.get('agencies', {})
                })
                
                # Chart data
                chart_data.append({"name": display_name, "value": data['total']})
                
            # Synthesize
            llm_response = synthesizer.synthesize("RANKING", ranking_data, message)
            
            if llm_response:
                # Add Chart Widget
                if chart_data:
                    title = "น้อยที่สุด" if parsed.intent == QueryIntent.RANKING_LEAST else "มากที่สุด"
                    chart_json = json.dumps({
                        "type": "bar",
                        "data": chart_data,
                        "title": f"สถิติ{title}"
                    }, ensure_ascii=False)
                    llm_response += f"\n\n<chart>{chart_json}</chart>"
                
                history[-1]["content"] = llm_response
                self.cache.save(message, llm_response, context=_cache_ctx())
                yield history, ""
                return
        
        # =====================================================================
        # Use ResponseSynthesizer for FILTER queries (e.g., "น้อยกว่า 50 แห่ง")
        # =====================================================================
        if parsed.intent in [QueryIntent.FILTER_LESS_THAN, QueryIntent.FILTER_GREATER_THAN, QueryIntent.FILTER_EQUALS]:
            
            threshold = parsed.threshold
            operator = parsed.threshold_operator or "<"
            
            if threshold is None:
                # Fallback if threshold wasn't detected
                history[-1]["content"] = "❌ ไม่สามารถระบุจำนวนที่ต้องการกรองได้ กรุณาระบุตัวเลข เช่น 'น้อยกว่า 50 แห่ง'"
                yield history, ""
                return
            
            # Filter data based on threshold
            filtered_data = []
            for name, data in aggregated.data:
                count = data.get('total', 0)
                if operator == "<" and count < threshold:
                    filtered_data.append((name, data))
                elif operator == ">" and count > threshold:
                    filtered_data.append((name, data))
                elif operator == "=" and count == threshold:
                    filtered_data.append((name, data))
            
            if not filtered_data:
                # ✨ Instead of just returning "not found", show the CLOSEST data
                op_text = "น้อยกว่า" if operator == "<" else ("มากกว่า" if operator == ">" else "เท่ากับ")
                level_text = "อำเภอ" if parsed.level == QueryLevel.DISTRICT else ("ตำบล" if parsed.level == QueryLevel.SUBDISTRICT else "จังหวัด")
                province_text = f"ใน{parsed.province}" if parsed.province else ""
                
                # Sort to find closest (for < get minimum, for > get maximum)
                if operator == "<":
                    sorted_data = sorted(aggregated.data, key=lambda x: x[1].get('total', 0))
                else:
                    sorted_data = sorted(aggregated.data, key=lambda x: x[1].get('total', 0), reverse=True)
                
                if sorted_data:
                    closest_name, closest_data = sorted_data[0]
                    closest_count = closest_data.get('total', 0)
                    
                    # Format name
                    display_name = closest_name
                    if '|' in closest_name:
                        parts = closest_name.split('|')
                        if len(parts) >= 2:
                            display_name = f"{parts[1]} ({parts[0]})"
                    
                    response = f"### 🔍 {level_text}ที่มีโรงเรียน{op_text} {threshold} แห่ง{province_text}\n\n"
                    response += f"ไม่มี{level_text}ที่มีโรงเรียน{op_text} **{threshold}** แห่งครับ 🤔\n\n"
                    response += f"**แต่ผมมีข้อมูลใกล้เคียงให้ครับ:**\n"
                    
                    if operator == "<":
                        response += f"• {level_text}ที่มีโรงเรียน**น้อยที่สุด**คือ **{display_name}** มี **{closest_count}** แห่ง\n"
                    else:
                        response += f"• {level_text}ที่มีโรงเรียน**มากที่สุด**คือ **{display_name}** มี **{closest_count}** แห่ง\n"
                    
                    # Show top 3 for context
                    if len(sorted_data) >= 3:
                        response += f"\n📊 **ลำดับ{level_text}ที่มีโรงเรียน{'น้อยสุด' if operator == '<' else 'มากสุด'}:**\n"
                        response += f"• {dn}: **{cnt}** แห่ง\n"
                    
                    new_threshold = closest_count + 10 if operator == "<" else max(1, closest_count - 10)
                    response += f"\n\n💡 **ลองถาม:** \"{level_text}ที่มีโรงเรียน{op_text} {new_threshold} แห่ง{province_text}\" หรือ \"{level_text}ไหนมีโรงเรียนน้อยที่สุด{province_text}\" ครับ 😊"
                    
                    history[-1]["content"] = response
                    self.cache.save(message, response, context=_cache_ctx())
                    yield history, ""
                    return
                else:
                    history[-1]["content"] = f"❌ ไม่พบข้อมูล{level_text}{province_text}"
                    yield history, ""
                    return
            
            # Sort by count
            if operator == "<":
                filtered_data.sort(key=lambda x: x[1].get('total', 0))  # Ascending
            else:
                filtered_data.sort(key=lambda x: x[1].get('total', 0), reverse=True)  # Descending
            
            # Build response
            op_text = "น้อยกว่า" if operator == "<" else ("มากกว่า" if operator == ">" else "เท่ากับ")
            level_text = "อำเภอ" if parsed.level == QueryLevel.DISTRICT else ("ตำบล" if parsed.level == QueryLevel.SUBDISTRICT else "จังหวัด")
            province_text = f"ใน{parsed.province}" if parsed.province else ""
            
            response = f"### 🔍 {level_text}ที่มีโรงเรียน{op_text} {threshold} แห่ง{province_text}\n\n"
            response += f"พบทั้งหมด **{len(filtered_data)} รายการ**:\n\n"
            
            chart_data = []
            for i, (name, data) in enumerate(filtered_data[:15], 1):
                display_name = name
                if '|' in name:
                    parts = name.split('|')
                    if len(parts) >= 2:
                        display_name = f"{parts[1]} ({parts[0]})"
                
                count = data.get('total', 0)
                response += f"{i}. **{display_name}**: {count} แห่ง\n"
                chart_data.append({"name": display_name, "value": count})
            
            response += f"\n✨ *พบข้อมูลทั้งหมด {len(filtered_data)} รายการ ครับ*"
            
            # Add chart
            if chart_data:
                chart_json = json.dumps({
                    "type": "bar",
                    "data": chart_data[:10],
                    "title": f"โรงเรียน{op_text} {threshold} แห่ง"
                }, ensure_ascii=False)
                response += f"\n\n<chart>{chart_json}</chart>"
            
            history[-1]["content"] = response
            self.cache.save(message, response, context=_cache_ctx())
            yield history, ""
            return
        
        # Format response
        history[-1]["content"] = ""
        full_response = ""
        for chunk in self.formatter.format(aggregated, parsed):
            full_response += chunk
            history[-1]["content"] = full_response
            yield history, ""
        
        # Add source info
        if results:
            collection_name = self.collections.get(parsed.level.value, "unknown")
            source_info = f"\n\n---\n*ข้อมูลจาก: {collection_name} ({len(results)} รายการ)*"
            history[-1]["content"] += source_info
            full_response += source_info
            
        self.cache.save(message, full_response, context=_cache_ctx())
        yield history, ""

    # =========================================================================
    # SCHOOL HANDLERS: School queries, counts, lists, and searches
    # =========================================================================






    # =========================================================================
    # SEARCH & AGGREGATION: Search execution and result aggregation
    # =========================================================================



