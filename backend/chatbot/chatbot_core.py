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

from .types import (
    QueryIntent, QueryLevel, ParsedQuery, SearchResult
)
from .constants import COLLECTION_NAMES
from .constants import COLLECTIONS, REGIONS, THAI_PROVINCES
from .security import input_sanitizer
from .llm import MultiProviderLLM
from .cache import HybridCache
from .query_parser import SmartQueryParser, ResponseSynthesizer
from .search_engine import SearchEngine
from .school_search import SchoolSearchEngine
from .aggregators import ResultAggregator
from .formatters import ResponseFormatter
from .memory import ConversationMemory
from .llm_agent import LLMAgent
from .context_manager import ContextManager

# Import handler mixins
from .handlers import LLMHandlersMixin, StatsHandlersMixin

logger = logging.getLogger(__name__)

# Model configuration
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant')  # 8b has separate quota
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')


# =============================================================================
# INITIALIZATION SECTION
# =============================================================================

class EducationChatbot(LLMHandlersMixin, StatsHandlersMixin):
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

    def _try_disambiguation_intercept(self, message: str, history: List[Dict[str, str]]) -> Optional[str]:
        """
        🆕 Intercept disambiguation selection patterns (e.g., "1", "ข้อ 2").
        Reads stored disambiguation choices from memory (persisted via Redis),
        then re-queries with the resolved school name.
        Returns formatted response string, or None if not a selection pattern.
        """
        import re
        msg = (message or "").strip()
        
        # Check if message is a selection pattern
        sel_match = re.fullmatch(r'(?:ข้อ|อันดับ|ลำดับ|เลือก|หมายเลข)?\s*(\d{1,2})\s*', msg)
        if not sel_match:
            return None
        
        selection_idx = int(sel_match.group(1))
        if selection_idx < 1 or selection_idx > 20:
            return None
        
        # Check if we have stored disambiguation choices in memory
        if not self.memory or not self.memory.last_disambig_choices:
            # Fallback: try parsing from last_ai_response in memory
            last_ai = getattr(self.memory, 'last_ai_response', '') if self.memory else ''
            if not last_ai:
                return None
            
            disambig_markers = [
                "กรุณาเลือก", "พบโรงเรียน", "พบชื่อที่ตรงกัน", "ชื่อใกล้เคียง",
                "ตอบเป็นลำดับ", "เลือกโรงเรียน", "พบโรงเรียนที่ตรงกัน"
            ]
            if not any(marker in last_ai for marker in disambig_markers):
                return None
            
            # Parse table from last_ai_response (4 columns: idx, name, province, district)
            table_rows = re.findall(
                r'\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|',
                last_ai
            )
            choices = []
            for row_idx_str, school_name, province, district in table_rows:
                try:
                    row_idx = int(row_idx_str)
                    choices.append({"idx": row_idx, "name": school_name.strip(), "province": province.strip(), "district": district.strip()})
                except ValueError:
                    continue
            if not choices:
                return None
            self.memory.last_disambig_choices = choices
        
        logger.info(f"📋 [DisambigIntercept] Detected selection: {selection_idx}")
        
        # Find the selected school from stored choices
        selected_school = None
        selected_province = None
        for choice in self.memory.last_disambig_choices:
            idx = choice.get("idx", 0)
            if idx == selection_idx:
                selected_school = choice.get("name", "")
                selected_province = choice.get("province", "")
                selected_district = choice.get("district", "")
                break
        
        if not selected_school:
            logger.warning(f"⚠️ [DisambigIntercept] No choice at index {selection_idx}")
            return None
        
        # Clean up province/district
        if selected_province in ["ไม่ระบุจังหวัด", "-", ""]:
            selected_province = None
        if selected_district in ["-", ""]:
            selected_district = None
        
        logger.info(f"📋 [DisambigIntercept] Selected: {selected_school} ({selected_province}, {selected_district})")
        
        # Reconstruct query with EXACT school name (not original query) to avoid re-disambiguation
        # Use the specific school name + province + district for precise matching
        reconstructed = f"ข้อมูลโรงเรียน{selected_school}"
        if selected_province:
            reconstructed += f" จังหวัด{selected_province}"
        if selected_district:
            reconstructed += f" อำเภอ{selected_district}"
        
        logger.info(f"📋 [DisambigIntercept] Reconstructed: {reconstructed}")
        
        # Update memory with selected school
        self.memory.last_school_name = selected_school
        if selected_province:
            self.memory.last_province = selected_province
        if selected_district:
            self.memory.last_district = selected_district
        # Clear disambiguation state
        self.memory.last_disambig_choices = None
        self.memory.last_disambig_query = None
        
        # Re-query: First try direct tool executor call (bypasses LLM re-disambiguation)
        try:
            if hasattr(self, 'llm_agent') and self.llm_agent and hasattr(self.llm_agent, 'tool_executor'):
                tool_result = self.llm_agent.tool_executor._get_school_full_details(
                    school_name=selected_school,
                    province=selected_province,
                    district=selected_district
                )
                if tool_result and tool_result.get("found"):
                    # Use synthesizer to format the raw result
                    # ResponseSynthesizer is already imported from .query_parser at top level, 
                    # but we re-import locally to be safe or just use it. 
                    # For safety against shadowing, we use the global oneline or import it correctly.
                    from .query_parser import ResponseSynthesizer
                    synthesizer = ResponseSynthesizer()
                    formatted = synthesizer.synthesize("TOOL_RESULT", tool_result, reconstructed)
                    if formatted:
                        logger.info(f"✅ [DisambigIntercept] Direct tool call succeeded for {selected_school}")
                        return formatted
                    # Fallback: basic formatting
                    lines = [f"📍 **{tool_result.get('school_name', selected_school)}**"]
                    if tool_result.get('province'):
                        lines.append(f"จังหวัด: {tool_result['province']}")
                    if tool_result.get('district'):
                        lines.append(f"อำเภอ/เขต: {tool_result['district']}")
                    if tool_result.get('total_students'):
                        lines.append(f"จำนวนนักเรียน: {tool_result['total_students']:,} คน")
                    if tool_result.get('total_teachers'):
                        lines.append(f"จำนวนครู: {tool_result['total_teachers']:,} คน")
                    if tool_result.get('agency'):
                        lines.append(f"สังกัด: {tool_result['agency']}")
                    if tool_result.get('student_breakdown'):
                        lines.append("\n**จำนวนนักเรียนจำแนกตามชั้น:**")
                        for grade, counts in tool_result['student_breakdown'].items():
                            total = counts if isinstance(counts, int) else counts.get('total', 0)
                            lines.append(f"- {grade}: {total:,} คน")
                    logger.info(f"✅ [DisambigIntercept] Direct formatted for {selected_school}")
                    return "\n".join(lines)
        except Exception as e:
            logger.warning(f"⚠️ [DisambigIntercept] Direct tool call failed: {e}")
        
        # Fallback: re-query via LLM agent
        try:
            if self.use_llm_agent and self.llm_agent:
                context = self.memory.to_dict() if self.memory else {}
                context["selected_school"] = selected_school
                if selected_province:
                    context["selected_province"] = selected_province
                if selected_district:
                    context["selected_district"] = selected_district
                
                llm_response, _ = self.llm_agent.process_query(reconstructed, context=context)
                if llm_response:
                    logger.info(f"✅ [DisambigIntercept] LLM fallback succeeded for {selected_school}")
                    return llm_response
        except Exception as e:
            logger.error(f"❌ [DisambigIntercept] LLM Agent failed: {e}")
        
        return None

    def _try_year_comparison_intercept(self, message: str) -> Optional[str]:
        """
        🆕 Intercept year-comparison queries before LLM agent.
        Detects patterns like "ปี 67 กับ 68" and calls compare_years directly.
        Returns formatted response string, or None if not a year comparison.
        """
        import re
        if not message:
            return None
        
        msg = message.strip()
        
        # Pattern: find 2 different year numbers in the message
        # Match Thai year formats: ปี 67, ปี 2567, 67, 2567
        year_pattern = r'(?:ปี\s*)?(\d{2,4})'
        year_matches = re.findall(year_pattern, msg)
        
        if len(year_matches) < 2:
            return None
        
        # Filter to valid years only
        from .constants import YEAR_ALIASES, AVAILABLE_YEARS
        valid_years = []
        for y in year_matches:
            normalized = YEAR_ALIASES.get(y, y)
            if normalized in AVAILABLE_YEARS and normalized not in valid_years:
                valid_years.append(normalized)
        
        if len(valid_years) < 2:
            return None
        
        # Check if this is actually a comparison context
        compare_keywords = [
            "เปรียบเทียบ", "เทียบ", "ต่างกัน", "แตกต่าง",
            "กับ", "vs", "เทียบกับ", "กี่คน", "กี่แห่ง",
            "เพิ่ม", "ลด", "เปลี่ยน", "ปี"
        ]
        if not any(kw in msg for kw in compare_keywords):
            return None
        
        year1, year2 = valid_years[0], valid_years[1]
        logger.info(f"📅 [YearIntercept] Detected year comparison: {year1} vs {year2}")
        
        # Extract province (if any)
        province = None
        # Common aliases first
        if "กรุงเทพ" in msg:
            province = "กรุงเทพมหานคร"
        elif hasattr(self, 'llm_agent') and self.llm_agent and hasattr(self.llm_agent, 'tool_executor'):
            # Use the tool executor's province normalization
            import re as re2
            # Try to find known province patterns: จังหวัดX, ในX, ของX
            prov_match = re2.search(r'(?:จังหวัด|ใน|ของ)\s*([ก-ฮ]+(?:[ก-ฮ]+)*)', msg)
            if prov_match:
                candidate = prov_match.group(1)
                # Filter out non-province words
                skip_words = ["ปี", "ประเทศ", "ภาค", "ทั้ง", "แต่ละ"]
                if candidate not in skip_words and len(candidate) >= 3:
                    province = candidate
        # Fallback to memory
        if not province and self.memory and self.memory.last_province:
            province = self.memory.last_province
        
        # Extract school name (if any)
        school_name = None
        school_keywords = ["โรงเรียน", "วิทยาลัย", "สถาบัน"]
        for kw in school_keywords:
            if kw in msg:
                # Extract school name after the keyword
                idx = msg.index(kw)
                remaining = msg[idx:]
                # Take until next space-separated keyword or year marker
                parts = remaining.split()
                if len(parts) >= 2:
                    # Take the school name part (skip common Thai suffixes/year markers)
                    school_parts = []
                    stop_words = ["มี", "มีนักเรียน", "มีครู", "ปี", "กี่", "เท่าไหร่", "เท่าไร",
                                  "นักเรียน", "ครู", "จำนวน", "เปรียบเทียบ", "กับ", "vs"]
                    for p in parts:
                        if p in stop_words or re.match(r'^\d{2,4}$', p):
                            break
                        school_parts.append(p)
                    school_name = " ".join(school_parts).strip()
                    if school_name == kw:
                        school_name = None
                break
        
        # Extract metric
        metric = "all"
        if "นักเรียน" in msg or "นร" in msg or "เด็ก" in msg:
            metric = "students"
        elif "ครู" in msg or "อาจารย์" in msg:
            metric = "teachers"
        elif "โรงเรียน" in msg and not school_name:
            metric = "schools"
        
        logger.info(f"📅 [YearIntercept] Params: province={province}, school={school_name}, metric={metric}")
        
        # Call the tool directly
        try:
            tool_result = self.llm_agent.tool_executor._compare_years(
                year1=year1,
                year2=year2,
                province=province,
                school_name=school_name,
                metric=metric,
            )
            
            if not tool_result or "error" in tool_result:
                error_msg = tool_result.get("error", "ไม่สามารถดึงข้อมูลได้") if tool_result else "ไม่สามารถดึงข้อมูลได้"
                return f"ขออภัยครับ {error_msg}"
            
            # Format response using LLM agent
            import json
            tool_data_str = json.dumps(tool_result, ensure_ascii=False, default=str)
            
            try:
                if hasattr(self, 'llm_agent') and self.llm_agent:
                    response = self.llm_agent._generate_response(
                        message,
                        [tool_result]
                    )
                else:
                    response = None
            except Exception as llm_err:
                logger.warning(f"⚠️ [YearIntercept] LLM formatting failed: {llm_err}")
                response = None
            
            if response:
                return response
            else:
                # Fallback: format manually
                y1_data = tool_result.get("year1", {})
                y2_data = tool_result.get("year2", {})
                diff = tool_result.get("difference", {})
                scope = tool_result.get("scope", "")
                
                lines = [f"📊 เปรียบเทียบข้อมูลปี {y1_data.get('year')} กับ {y2_data.get('year')} ({scope})\n"]
                for key in ["schools", "students", "teachers"]:
                    if key in diff:
                        d = diff[key]
                        label = {"schools": "โรงเรียน", "students": "นักเรียน", "teachers": "ครู"}.get(key, key)
                        v1 = y1_data.get("data", {}).get(key, 0)
                        v2 = y2_data.get("data", {}).get(key, 0)
                        lines.append(f"- {label}: ปี {y1_data.get('year')} = **{v1:,}** → ปี {y2_data.get('year')} = **{v2:,}** ({d['direction']} {abs(d['change']):,}, {d['percent_change']}%)")
                
                return "\n".join(lines)
                
        except Exception as e:
            logger.error(f"❌ [YearIntercept] Error: {e}")
            return None

    def _should_use_llm_context(self, message: str, history: List[Dict[str, str]]) -> bool:
        """
        Decide when to invoke LLM-based ContextManager.
        Hybrid strategy: use LLM only for ambiguous follow-ups or selections.
        """
        msg = (message or "").strip().lower()
        if not msg:
            return False

        # 1) Direct selection patterns (e.g., "ข้อ 2", "2")
        if re.fullmatch(r'(?:ข้อ|อันดับ|ลำดับ)?\s*\d+', msg):
            return True

        # 2) Pronouns / deictic references
        pronouns = [
            "ที่นั่น", "ที่นั้น", "ตรงนั้น", "อันนี้", "อันนั้น", "อันแรก",
            "อันที่", "อีกอัน", "อีกโรง", "โรงเรียนนั้น", "โรงเรียนนี้",
            "ที่กล่าวมา", "ที่พูดถึง", "ของมัน", "ของเขา"
        ]
        if any(p in msg for p in pronouns):
            return True

        # 3) Short follow-up without explicit entity
        follow_up_words = [
            "แล้ว", "ล่ะ", "ต่อ", "อีก", "เพิ่ม", "เหมือนกัน", "สรุป",
            "บ้าง", "ทั้งหมด", "เท่าไหร่", "กี่", "ที่ไหน", "รายละเอียด",
            "ล่าสุด", "ปีล่าสุด", "ปีนี้"
        ]
        is_short = len(msg) <= 35
        has_follow = any(w in msg for w in follow_up_words)

        # 3a) Strong follow-up prefix — always use context even if entity present
        #     e.g., "แล้วโรงเรียนละจังหวัดไหน" starts with "แล้ว" → follow-up
        strong_prefixes = ["แล้ว", "ส่วน", "แต่", "ถ้า", "แต่ว่า"]
        starts_with_follow = any(msg.startswith(p) for p in strong_prefixes)
        if is_short and starts_with_follow and history:
            return True

        # Detect explicit entities (province/school/agency keywords)
        has_entity = any(k in msg for k in [
            "โรงเรียน", "อำเภอ", "ตำบล", "เขต", "สพฐ", "สช", "อปท", "สพป", "สพม", "จังหวัด"
        ])
        if not has_entity:
            for prov in THAI_PROVINCES:
                if prov.lower() in msg:
                    has_entity = True
                    break

        if is_short and has_follow and not has_entity:
            return True

        # 4) If last assistant asked for clarification/selection
        last_ai = ""
        for m in reversed(history):
            if m.get("role") == "assistant":
                last_ai = m.get("content", "")
                break
        if last_ai:
            clarification_markers = [
                "คุณหมายถึง", "เลือกเลขข้อ", "โปรดเลือก", "กรุณาเลือก",
                "พบโรงเรียน", "มีชื่อใกล้เคียง", "พิมพ์เลือกเลขข้อ"
            ]
            if any(marker in last_ai for marker in clarification_markers):
                return True

        # 5) If we have memory but message is short and vague
        if self.memory and (self.memory.last_school_name or self.memory.last_province):
            if is_short and not has_entity:
                if any(w in msg for w in ["ที่ไหน", "เท่าไหร่", "กี่", "อะไร", "บ้าง", "รายละเอียด"]):
                    return True

        return False

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
        
        if is_school_specific_query:
            logger.info(f"🏫 School-specific query detected (school_name: {self.memory.last_school_name}) - skipping cache")
        
        # Check Semantic Cache (disabled for testing)
        if DEBUG_DISABLE_CACHE:
            logger.info("🔧 Cache DISABLED by env (ENABLE_SEMANTIC_CACHE=0)")
        elif not is_school_specific_query and self.cache and not was_coreference_resolved:
            cached_response = self.cache.check(message)
            if cached_response:
                # CRITICAL: Still update memory on cache hit so follow-up queries retain context
                try:
                    cache_parsed = self.parser.parse(message)
                    if cache_parsed:
                        self.memory.update(cache_parsed, original_query=message)
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
            
            if "GENERAL" in intent_type and not has_strong_edu_keyword:
                # UNIFIED MODE: Respond directly with LLM for general/casual queries
                logger.info(f"🌐 General intent detected - responding with LLM directly")
                try:
                    general_response = self._generate_general_response(message)
                    if general_response:
                        history[-1]["content"] = general_response
                        self.cache.save(message, general_response)
                        yield history, ""
                        return
                except Exception as e:
                    logger.warning(f"⚠️ General LLM response failed: {e}")
                # Fall through to LLM Agent if general response fails

        # 🆕 INTERCEPTOR: Year comparison queries → direct tool call (bypass LLM)
        year_compare_result = self._try_year_comparison_intercept(message)
        if year_compare_result:
            history[-1]["content"] = year_compare_result
            self.cache.save(message, year_compare_result)
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
            
            
            agent_response = self.process_with_llm_agent(
                message, 
                rich_context=rich_context_dict, 
                session_context=ctx, 
                session_id=session_key
            )
            
            if agent_response:
                history[-1]["content"] = agent_response
                self.cache.save(message, agent_response)
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
            self.cache.save(message, ratio_result)
            yield history, ""
            return

        # 🆕 Handle Teacher Count Queries FIRST (ครู, อาจารย์) - takes priority over student
        teacher_result = self._handle_teacher_count_query(parsed, message)
        if teacher_result:
            history[-1]["content"] = teacher_result
            self.cache.save(message, teacher_result)
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
                self.cache.save(message, response_text)
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
                self.cache.save(message, llm_response)
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
                    self.cache.save(message, response)
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
            self.cache.save(message, response)
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
            
        self.cache.save(message, full_response)
        yield history, ""

    # =========================================================================
    # SCHOOL HANDLERS: School queries, counts, lists, and searches
    # =========================================================================

    def _handle_school_query(self, parsed: ParsedQuery, message: str, history: List) -> Optional[str]:
        """Handle school-related queries"""
        school_engine = SchoolSearchEngine(self.qdrant_client, llm_provider=self.model)
        synthesizer = ResponseSynthesizer()
        response_text = ""
        
        if parsed.intent == QueryIntent.SCHOOL_DETAIL:
            school_name = parsed.school_name
            
            if not school_name:
                query_lower = message.lower()
                phrases_to_remove = [
                    'ข้อมูลโรงเรียน', 'รายละเอียดโรงเรียน', 'เบอร์โทรโรงเรียน',
                    'ที่อยู่โรงเรียน', 'ติดต่อโรงเรียน', 'โรงเรียน', 'ร.ร.', 'รร.',
                    'อยู่ที่ไหน', 'อยู่ตรงไหน', 'อยู่ไหน', 'ตั้งอยู่ที่ไหน',
                    'ขอข้อมูล', 'ขอรายละเอียด', 'ขอดู', 'หา', 'ค้นหา',
                    'ครับ', 'ค่ะ', 'หน่อย', 'ได้ไหม', 'มั้ย', 'บ้าง',
                    'ที่ตั้ง', 'ที่อยู่', 'ของ', 'ที่', 'ขอ',
                    # Additional phrases to remove
                    'รายละเอียด', 'ข้อมูล', 'เบอร์โทร', 'เบอร์', 'โทรศัพท์',
                    'ติดต่อ', 'สอบถาม', 'ดู', 'แสดง', 'บอก', 'ช่วย'
                ]
                school_name = query_lower
                for phrase in phrases_to_remove:
                    school_name = school_name.replace(phrase, '')
                school_name = ' '.join(school_name.split()).strip()
            
            if school_name:
                details = school_engine.get_school_details(school_name)
                if details:
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
                        }
                    }
                    
                    llm_response = synthesizer.synthesize("SCHOOL_DETAIL", data, message)
                    
                    if llm_response:
                        response_text = llm_response
                    else:
                        # Fallback template with น้องดีโอ personality
                        address = f"ต.{details.get('subdistrict', '-')} อ.{details.get('district', '-')} จ.{details.get('province', '-')}"
                        response_text = f"📍 **ข้อมูลโรงเรียน{details.get('school_name')}**\n\n"
                        response_text += f"สวัสดีครับพี่! น้องดีโอหาข้อมูลมาให้แล้วนะครับ 😊\n\n"
                        response_text += f"🏫 **ชื่อ**: {details.get('school_name')}\n"
                        response_text += f"📌 **ที่ตั้ง**: {address}\n"
                        response_text += f"🏛️ **สังกัด**: {details.get('agency')}\n"
                        if details.get('phone1'):
                            response_text += f"📞 **โทรศัพท์**: {details.get('phone1')}\n"
                    
                    # Add map if coordinates available
                    lat = details.get('latitude')
                    lng = details.get('longitude')
                    if lat and lng:
                        try:
                            address = f"ต.{details.get('subdistrict', '-')} อ.{details.get('district', '-')} จ.{details.get('province', '-')}"
                            map_json = json.dumps({
                                "latitude": float(lat),
                                "longitude": float(lng), 
                                "schoolName": details.get('school_name', school_name),
                                "address": address
                            }, ensure_ascii=False)
                            response_text += f"\n<map>{map_json}</map>"
                        except:
                            pass
                    
                    response_text += f"\n\n💡 **คำถามที่น่าสนใจ**\n"
                    response_text += f"• รายชื่อโรงเรียนในอำเภอ{details.get('district', '')}?\n"
                    response_text += f"• จังหวัด{details.get('province', '')}มีโรงเรียนกี่แห่ง?\n"
                else:
                    response_text = f"❌ ไม่พบข้อมูลโรงเรียน \"{school_name}\" ในฐานข้อมูล\n\n💡 ลองค้นหาด้วยชื่ออื่น"
            else:
                response_text = "❓ กรุณาระบุชื่อโรงเรียนที่ต้องการค้นหา"
                
        elif parsed.intent == QueryIntent.SCHOOL_COUNT:
            response_text = self._handle_school_count(parsed, message, school_engine, synthesizer)
            
        elif parsed.intent == QueryIntent.SCHOOL_LIST:
            response_text = self._handle_school_list(parsed, message, school_engine, synthesizer, history)
            
        elif parsed.intent == QueryIntent.SCHOOL_SEARCH:
            response_text = self._handle_school_search(parsed, message, school_engine, history)
        
        return response_text

    def _handle_school_count(self, parsed: ParsedQuery, message: str, school_engine: SchoolSearchEngine, synthesizer: ResponseSynthesizer) -> str:
        """Handle school count queries"""
        data = {"query_type": "school_count", "location": {}, "counts": {}, "sample_schools": []}
        
        # DEBUG: Log parsed entities
        logger.info(f"🔍 Parsed: agency={parsed.agency}, province={parsed.province}, district={parsed.district}, region={parsed.region}")
        
        # Handle subdistrict-level queries (search in statistics collection)
        if parsed.subdistrict:
            # Search for subdistrict in statistics
            try:
                
                # Filter by metadata.subdistrict
                search_result = school_engine.client.scroll(
                    collection_name="education_statistics_subdistrict",
                    scroll_filter=Filter(
                        must=[
                            FieldCondition(
                                key="metadata.subdistrict",
                                match=MatchValue(value=parsed.subdistrict)
                            )
                        ]
                    ),
                    limit=20,
                    with_payload=True
                )
                
                total_count = 0
                province = None
                district = None
                subdistrict = parsed.subdistrict
                agencies_breakdown = {}
                
                for point in search_result[0]:
                    meta = point.payload.get('metadata', {})
                    if not province:
                        province = meta.get('province')
                        district = meta.get('district')
                    
                    # Get count from metadata
                    count = meta.get('count', 0)
                    agency = meta.get('agency')
                    
                    if agency:
                        # This is agency breakdown record
                        agencies_breakdown[agency] = agencies_breakdown.get(agency, 0) + count
                    elif meta.get('stat_type') == 'subdistrict_total':
                        # This is total count record
                        total_count = count
                
                # Calculate total from agencies if not set
                if total_count == 0 and agencies_breakdown:
                    total_count = sum(agencies_breakdown.values())
                
                if total_count > 0:
                    data["location"] = {"province": province, "district": district, "subdistrict": subdistrict}
                    data["counts"] = {"total": int(total_count), "agencies": agencies_breakdown}
                    
                    # Get sample schools from education_schools
                    sample_results = school_engine.client.scroll(
                        collection_name=COLLECTION_NAMES["schools"],
                        scroll_filter=Filter(
                            must=[
                                FieldCondition(
                                    key="metadata.subdistrict",
                                    match=MatchValue(value=subdistrict)
                                )
                            ]
                        ),
                        limit=10,
                        with_payload=True
                    )
                    
                    sample_schools = []
                    for s in sample_results[0]:
                        meta = s.payload.get('metadata', {})
                        sample_schools.append({
                            "name": meta.get('school_name'),
                            "district": meta.get('district'),
                            "subdistrict": meta.get('subdistrict')
                        })
                    data["sample_schools"] = sample_schools
                    
            except Exception as e:
                logger.warning(f"⚠️ Subdistrict search error: {e}")
        
        elif parsed.province:
            count = school_engine.count_schools(
                province=parsed.province,
                district=parsed.district,
                agency=parsed.agency
            )
            
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
                    "subdistrict": meta.get('subdistrict'),
                    "agency": meta.get('agency')  # Add agency to sample
                })
            
            # Get agency breakdown for the province
            agency_breakdown = {}
            subdistrict_breakdown = {}  # New: breakdown by subdistrict for district-level queries
            
            try:
                
                # Build filter conditions
                filter_conditions = [
                    FieldCondition(key="metadata.province", match=MatchValue(value=parsed.province))
                ]
                if parsed.district:
                    filter_conditions.append(
                        FieldCondition(key="metadata.district", match=MatchValue(value=parsed.district))
                    )
                
                scroll_result = school_engine.client.scroll(
                    collection_name=COLLECTION_NAMES["schools"],
                    scroll_filter=Filter(must=filter_conditions),
                    limit=2000,
                    with_payload=["metadata.agency", "metadata.subdistrict", "metadata.school_name"]
                )
                
                seen_schools = set()
                for point in scroll_result[0]:
                    meta = point.payload.get('metadata', {})
                    school_name = meta.get('school_name', '')
                    
                    if school_name not in seen_schools:
                        seen_schools.add(school_name)
                        
                        # Agency breakdown
                        agency = meta.get('agency')
                        if agency:
                            agency_breakdown[agency] = agency_breakdown.get(agency, 0) + 1
                        
                        # Subdistrict breakdown (only for district-level queries)
                        if parsed.district:
                            subdistrict = meta.get('subdistrict')
                            if subdistrict:
                                subdistrict_breakdown[subdistrict] = subdistrict_breakdown.get(subdistrict, 0) + 1
                
            except Exception as e:
                logger.warning(f"⚠️ Breakdown error: {e}")
            
            data["location"] = {"province": parsed.province, "district": parsed.district, "agency": parsed.agency}
            counts_data = {"total": count, "agency_breakdown": agency_breakdown}
            
            # Add subdistrict breakdown for district-level queries
            if parsed.district and subdistrict_breakdown:
                # Sort by count descending
                sorted_subdistricts = sorted(subdistrict_breakdown.items(), key=lambda x: x[1], reverse=True)
                counts_data["subdistrict_breakdown"] = [{"subdistrict": s, "count": c} for s, c in sorted_subdistricts]
            
            data["counts"] = counts_data
            data["sample_schools"] = sample_schools
            
        elif parsed.region and parsed.region != "each_region":
            provinces_in_region = REGIONS.get(parsed.region, [])
            total_count = 0
            province_breakdown = []
            agency_breakdown = {}
            sample_schools = []
            
            for province in provinces_in_region:
                count = school_engine.count_schools(province=province, agency=parsed.agency)
                total_count += count
                if count > 0:
                    province_breakdown.append({"province": province, "count": count})
                
                # Collect agency counts from this province
                try:
                    agency_scroll = school_engine.client.scroll(
                        collection_name=COLLECTION_NAMES["schools"],
                        scroll_filter=Filter(must=[
                            FieldCondition(key="metadata.province", match=MatchValue(value=province))
                        ]),
                        limit=500,
                        with_payload=["metadata.agency"]
                    )
                    for point in agency_scroll[0]:
                        agency = point.payload.get('metadata', {}).get('agency')
                        if agency:
                            agency_breakdown[agency] = agency_breakdown.get(agency, 0) + 1
                except:
                    pass
            
            # Get sample schools from first province with data
            for province in provinces_in_region:
                if not sample_schools:
                    samples = school_engine.search_by_province(province, parsed.agency, limit=10)
                    for s in samples:
                        meta = s.payload.get('metadata', {})
                        sample_schools.append({
                            "name": meta.get('school_name'),
                            "district": meta.get('district'),
                            "province": meta.get('province'),
                            "agency": meta.get('agency')
                        })
                    if sample_schools:
                        break
            
            data["location"] = {"region": parsed.region, "agency": parsed.agency}
            data["counts"] = {
                "total": total_count,
                "province_breakdown": sorted(province_breakdown, key=lambda x: x['count'], reverse=True)[:10],
                "agency_breakdown": agency_breakdown
            }
            data["sample_schools"] = sample_schools
        
        # Handle national/country-wide queries (ทั้งประเทศ, ประเทศไทย) - NOT agency-only
        elif not parsed.province and not parsed.district and not parsed.region and not parsed.agency:
            # Check if this looks like a national query
            national_keywords = ['ประเทศ', 'ทั้งประเทศ', 'ทั่วประเทศ', 'ไทย']
            is_national = any(kw in message for kw in national_keywords)
            
            if is_national:
                total_count = 0
                agency_breakdown = {}
                sample_schools = []
                
                # Aggregate across all regions
                for region_name, provinces in REGIONS.items():
                    if region_name in ['ภาคอีสาน', 'ภาคอีสาน']:  # Skip aliases
                        continue
                    for province in provinces:
                        count = school_engine.count_schools(province=province)
                        total_count += count
                        
                        # Get agency breakdown
                        try:
                            agency_scroll = school_engine.client.scroll(
                                collection_name=COLLECTION_NAMES["schools"],
                                scroll_filter=Filter(must=[
                                    FieldCondition(key="metadata.province", match=MatchValue(value=province))
                                ]),
                                limit=200,
                                with_payload=["metadata.agency"]
                            )
                            for point in agency_scroll[0]:
                                agency = point.payload.get('metadata', {}).get('agency')
                                if agency:
                                    agency_breakdown[agency] = agency_breakdown.get(agency, 0) + 1
                        except:
                            pass
                
                # Get sample schools from one province
                samples = school_engine.search_by_province("กรุงเทพมหานคร", limit=10)
                for s in samples:
                    meta = s.payload.get('metadata', {})
                    sample_schools.append({
                        "name": meta.get('school_name'),
                        "district": meta.get('district'),
                        "province": meta.get('province'),
                        "agency": meta.get('agency')
                    })
                
                data["location"] = {"country": "ประเทศไทย"}
                data["counts"] = {"total": total_count, "agency_breakdown": agency_breakdown}
                data["sample_schools"] = sample_schools
        
        # Handle agency-only queries (e.g., "สพฐ มีกี่โรงเรียน")
        elif parsed.agency and not parsed.province and not parsed.region:
            # Count schools by agency nationwide
            
            total_count = 0
            sample_schools = []
            province_breakdown = {}
            
            # Count all schools with this agency
            scroll_result = school_engine.client.scroll(
                collection_name=COLLECTION_NAMES["schools"],
                scroll_filter=Filter(must=[
                    FieldCondition(key="metadata.agency", match=MatchValue(value=parsed.agency))
                ]),
                limit=5000,
                with_payload=["metadata.province", "metadata.school_name", "metadata.district"]
            )
            
            seen_schools = set()
            for point in scroll_result[0]:
                meta = point.payload.get('metadata', {})
                school_name = meta.get('school_name', '')
                if school_name not in seen_schools:
                    seen_schools.add(school_name)
                    total_count += 1
                    
                    # Province breakdown
                    province = meta.get('province', 'ไม่ระบุ')
                    province_breakdown[province] = province_breakdown.get(province, 0) + 1
                    
                    # Collect samples
                    if len(sample_schools) < 10:
                        sample_schools.append({
                            "name": school_name,
                            "district": meta.get('district'),
                            "province": province
                        })
            
            # Sort province breakdown by count
            sorted_provinces = sorted(province_breakdown.items(), key=lambda x: x[1], reverse=True)[:10]
            
            data["location"] = {"agency": parsed.agency}
            data["counts"] = {"total": total_count, "province_breakdown": [{"province": p, "count": c} for p, c in sorted_provinces]}
            data["sample_schools"] = sample_schools
        
        # DEBUG: Log data before synthesize
        logger.info(f"📦 Data for synthesize: total={data['counts'].get('total', 0)}, samples={len(data.get('sample_schools', []))}")
        
        llm_response = synthesizer.synthesize("SCHOOL_COUNT", data, message)
        
        if llm_response:
            return llm_response
        else:
            # Smart fallback template - context-aware and natural
            total_count = data['counts'].get('total', 0)
            
            # Build location description
            if parsed.region:
                location_desc = f"ภาค{parsed.region.replace('ภาค', '')}"
            elif parsed.district and parsed.province:
                location_desc = f"เขต/อำเภอ{parsed.district} จังหวัด{parsed.province}"
            elif parsed.province:
                location_desc = f"จังหวัด{parsed.province}"
            else:
                location_desc = "ทั่วประเทศไทย"
            
            # Add agency context
            if parsed.agency:
                location_desc += f" สังกัด{parsed.agency}"
            
            # Natural intro based on context
            response = f"📊 **ข้อมูลโรงเรียนใน{location_desc}**\n\n"
            response += f"พบโรงเรียนทั้งหมด **{total_count:,}** แห่ง"
            
            # Add context-specific observation
            if total_count > 1000:
                response += " ซึ่งถือว่าเป็นพื้นที่ที่มีโรงเรียนจำนวนมาก"
            elif total_count > 100:
                response += " ครอบคลุมหลายพื้นที่ในเขตนี้"
            elif total_count > 0:
                response += ""
            response += "\n\n"
            
            # Add agency breakdown if available
            if data['counts'].get('agency_breakdown'):
                response += "🏛️ **แยกตามสังกัด**\n"
                sorted_agencies = sorted(data['counts']['agency_breakdown'].items(), key=lambda x: x[1], reverse=True)
                for agency, count in sorted_agencies[:5]:
                    response += f"• {agency}: {count:,} แห่ง\n"
                response += "\n"
            
            # Add subdistrict breakdown for district queries
            if data['counts'].get('subdistrict_breakdown'):
                response += "🗺️ **แยกตามตำบล/แขวง**\n"
                for item in data['counts']['subdistrict_breakdown'][:8]:
                    response += f"• {item['subdistrict']}: {item['count']:,} แห่ง\n"
                response += "\n"
            
            # Add province breakdown for region queries
            if data['counts'].get('province_breakdown'):
                response += "📈 **แยกตามจังหวัด**\n"
                for i, p in enumerate(data['counts']['province_breakdown'][:5], 1):
                    response += f"{i}. {p['province']}: {p['count']:,} แห่ง\n"
                response += "\n"
            
            # Add sample schools if available
            if data.get("sample_schools"):
                response += "🏫 **ตัวอย่างโรงเรียน**\n"
                for school in data["sample_schools"][:5]:
                    name = school.get("name", "-")
                    district = school.get("district", "")
                    subdistrict = school.get("subdistrict", "")
                    loc_part = subdistrict or district
                    response += f"• {name}"
                    if loc_part:
                        response += f" ({loc_part})"
                    response += "\n"
                response += "\n"
            
            # Smart follow-up suggestions
            response += "💡 **สามารถถามต่อได้**\n"
            if parsed.district:
                response += f"• ตำบลไหนใน{parsed.district}มีโรงเรียนมากที่สุด?\n"
                response += f"• โรงเรียนเอกชนใน{parsed.district}มีกี่แห่ง?\n"
            elif parsed.province:
                response += f"• อำเภอไหนใน{parsed.province}มีโรงเรียนมากที่สุด?\n"
                response += f"• โรงเรียนสังกัด สพฐ ใน{parsed.province}มีกี่แห่ง?\n"
            elif parsed.region:
                response += f"• จังหวัดไหนใน{parsed.region}มีโรงเรียนน้อยที่สุด?\n"
                response += f"• โรงเรียนเอกชนใน{parsed.region}มีกี่แห่ง?\n"
            elif parsed.agency:
                response += f"• จังหวัดไหนมี{parsed.agency}มากที่สุด?\n"
                response += "• ภาคไหนมีโรงเรียนสังกัดนี้มากที่สุด?\n"
            
            return response

    def _handle_school_list(self, parsed: ParsedQuery, message: str, school_engine: SchoolSearchEngine, synthesizer: ResponseSynthesizer, history: List) -> str:
        """Handle school list queries"""
        data = {"query_type": "school_list", "location": {}, "total": 0, "schools": [], "district_breakdown": []}
        results = []
        location = ""
        total = 0
        
        if parsed.subdistrict:
            # Handle subdistrict search (PRIORITY)
            results = school_engine.search_by_subdistrict(
                province=parsed.province, 
                subdistrict=parsed.subdistrict, 
                district=parsed.district,
                agency=parsed.agency,
                limit=15
            )
            location = f"ต.{parsed.subdistrict}"
            if parsed.district: location += f" อ.{parsed.district}"
            if parsed.province: location += f" จ.{parsed.province}"
            
            # Count for subdistrict (approximate since no dedicated count method yet, use len(results) or search all)
            # For now, we will trust the search result length or implement count later if needed. 
            # But the UI expects 'total'. Let's do a quick count by fetching more keys if needed, 
            # or just use len(results) if < limit. 
            # Actually, let's just use the length of results for now as subdistricts rarely have > 15 schools.
            total = len(results) 
            # If we hit limit, we might want to know if there are more... 
            # Optimally we should add count_schools_by_subdistrict, but for now let's assume < 15 or close enough.
            
            data["location"] = {
                "province": parsed.province, 
                "district": parsed.district, 
                "subdistrict": parsed.subdistrict,
                "agency": parsed.agency
            }

        elif parsed.district and parsed.province:
            results = school_engine.search_by_district(parsed.province, parsed.district, parsed.agency, limit=15)
            location = f"อ.{parsed.district} จ.{parsed.province}"
            total = school_engine.count_schools(parsed.province, parsed.district, parsed.agency)
            data["location"] = {"province": parsed.province, "district": parsed.district, "agency": parsed.agency}
            
        elif parsed.province:
            results = school_engine.search_by_province(parsed.province, parsed.agency, limit=15)
            location = f"จ.{parsed.province}"
            total = school_engine.count_schools(parsed.province, agency=parsed.agency)
            data["location"] = {"province": parsed.province, "agency": parsed.agency}
            
        elif parsed.region and parsed.region != "each_region":
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
            return "❓ กรุณาระบุจังหวัด อำเภอ หรือภูมิภาคที่ต้องการค้นหา"
        
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
            llm_response = synthesizer.synthesize("SCHOOL_LIST", data, message)
            
            if llm_response:
                response_text = llm_response
                if total > 15:
                    response_text += f"\n\n💡 **พิมพ์ \"ดูเพิ่มเติม\" เพื่อดูโรงเรียนต่อไป** (เหลืออีก {total - 15:,} แห่ง)"
            else:
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
            
            return response_text
        else:
            return f"❌ ไม่พบโรงเรียนใน{location}"

    def _handle_school_search(self, parsed: ParsedQuery, message: str, school_engine: SchoolSearchEngine, history: List) -> str:
        """Handle school search by name"""
        # If region or province specified without school name, redirect to list
        if (parsed.region or parsed.province) and not parsed.school_name:
            synthesizer = ResponseSynthesizer()
            return self._handle_school_list(parsed, message, school_engine, synthesizer, history)
        
        # Clean school name
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
                return response_text
            else:
                # Try fuzzy matching
                similar_schools = school_engine.find_similar_schools(school_name, province=parsed.province, top_k=5)
                
                if similar_schools:
                    response_text = f"🤔 **คุณหมายถึง...?** (ไม่พบ \"{school_name}\" ตรงๆ)\n\n"
                    response_text += "📋 **โรงเรียนที่ใกล้เคียง:**\n"
                    for i, school in enumerate(similar_schools, 1):
                        score_pct = int(school['score'] * 100)
                        response_text += f"{i}. **{school['name']}** ({score_pct}% ตรงกัน)\n"
                        response_text += f"   📍 อ.{school['district']} จ.{school['province']}\n\n"
                    response_text += "\n💡 *ลองคลิกหรือพิมพ์ชื่อที่ถูกต้องอีกครั้งนะครับ*"
                    return response_text
                else:
                    return self._rag_fallback(message)
        else:
            return self._rag_fallback(message)

    def _handle_load_more(self) -> str:
        """Handle load more pagination"""
        last_query = getattr(self.memory, 'last_school_list_query', None)
        current_offset = getattr(self.memory, 'last_school_list_offset', 0)
        
        if last_query and current_offset > 0:
            school_engine = SchoolSearchEngine(self.qdrant_client)
            
            # --- Advanced Search Pagination ---
            if last_query.get('type') == 'advanced_criteria':
                filters = last_query.get('filters', {})
                total = last_query.get('total', 0)
                
                # Fetch next page using same criteria
                results, _, _ = school_engine.search_by_criteria(filters, limit=15, offset=current_offset)
                
                if results:
                    criteria_text = []
                    if filters.get('min_students'): criteria_text.append(f"นักเรียน > {filters['min_students']}")
                    if filters.get('area_name'): criteria_text.append(f"สังกัด {filters['area_name']}")
                    criteria_str = ", ".join(criteria_text)
                    
                    response_text = f"📚 **ผลการค้นหาต่อ** ({criteria_str}):\n\n"
                    
                    for i, hit in enumerate(results, current_offset + 1):
                        meta = hit.payload.get('metadata', {})
                        school_name = meta.get('school_name', 'ไม่ระบุ')
                        summ = f"{meta.get('total_students', 0)} คน" if filters.get('min_students') or filters.get('max_students') else ""
                        response_text += f"{i}. **{school_name}** {summ}\n"
                    
                    new_offset = current_offset + len(results)
                    remaining = total - new_offset
                    
                    if remaining > 0:
                        response_text += f"\n*...และอีก {remaining:,} แห่ง*"
                        response_text += f"\n\n💡 **พิมพ์ \"ดูเพิ่มเติม\" เพื่อดูต่อ**"
                        self.memory.last_school_list_offset = new_offset
                    else:
                        response_text += f"\n\n✅ **แสดงครบทั้งหมดแล้ว!**"
                        self.memory.last_school_list_offset = 0
                        self.memory.last_school_list_query = None
                    
                    return response_text
                else:
                    self.memory.last_school_list_offset = 0
                    return "✅ **แสดงครบทั้งหมดแล้ว!**"

            # --- Compatible Legacy Pagination ---
            province = last_query.get('province')
            district = last_query.get('district')
            agency = last_query.get('agency')
            total = last_query.get('total', 0)
            
            if district and province:
                all_results = school_engine.search_by_district(province, district, agency, limit=total)
            elif province:
                all_results = school_engine.search_by_province(province, agency, limit=total)
            else:
                all_results = []
            
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
                
                return response_text
            else:
                self.memory.last_school_list_offset = 0
                return "✅ **แสดงครบทั้งหมดแล้ว!**"
        else:
            return "❓ ไม่มีข้อมูลให้แสดงเพิ่มเติม กรุณาค้นหารายชื่อโรงเรียนใหม่ก่อน"

    # =========================================================================
    # SEARCH & AGGREGATION: Search execution and result aggregation
    # =========================================================================

    def _execute_search(self, parsed: ParsedQuery, message: str, history: List) -> Optional[List]:
        """Execute search based on intent"""
        query_lower = message.lower()
        
        # Advanced / Comprehensive Search (Students, Teachers, Area, etc.)
        is_advanced_search = any([
            parsed.min_students is not None,
            parsed.max_students is not None,
            parsed.min_teachers is not None,
            parsed.max_teachers is not None,
            parsed.area_name is not None,
            parsed.coordinates_intent
        ])
        
        if is_advanced_search:
             synthesizer = ResponseSynthesizer()
             return self._handle_advanced_search(parsed, message, self.search_engine, synthesizer, history)

        # Ranking queries (includes FILTER intents as they need same search approach)
        is_ranking_or_filter = parsed.intent in [
            QueryIntent.RANKING_MOST, QueryIntent.RANKING_LEAST,
            QueryIntent.FILTER_LESS_THAN, QueryIntent.FILTER_GREATER_THAN, QueryIntent.FILTER_EQUALS
        ]
        
        if is_ranking_or_filter:
            # Determine search level
            agency_ranking_kw = ['สังกัดไหน', 'สังกัดใด', 'สังกัดอะไร', 'สังกัดที่มี', 
                                 'หน่วยงานไหน', 'หน่วยงานใด', 'หน่วยงานอะไร', 'สังกัดการศึกษา']
            
            if any(kw in query_lower for kw in agency_ranking_kw):
                if parsed.province or parsed.region:
                    search_level = QueryLevel.PROVINCE
                else:
                    search_level = QueryLevel.AGENCY
            elif 'จังหวัดไหน' in query_lower or 'จังหวัดใด' in query_lower:
                search_level = QueryLevel.PROVINCE
            elif 'อำเภอไหน' in query_lower or 'อำเภอใด' in query_lower or 'เขตไหน' in query_lower:
                search_level = QueryLevel.DISTRICT
            elif 'ตำบลไหน' in query_lower or 'ตำบลใด' in query_lower or 'แขวงไหน' in query_lower:
                search_level = QueryLevel.SUBDISTRICT
            else:
                search_level = parsed.level

            # Guard: district/subdistrict ranking needs a province/region scope
            if search_level in [QueryLevel.DISTRICT, QueryLevel.SUBDISTRICT] and not parsed.province and not parsed.region:
                history[-1]["content"] = "ต้องการจัดอันดับในจังหวัดไหนครับ"
                return None
            
            parsed.level = search_level
            
            collection_name = self.collections.get(search_level.value)
            if not collection_name:
                history[-1]["content"] = f"❌ ไม่พบฐานข้อมูลระดับ {search_level.value}"
                return None
            
            return self.search_engine.ranking_search(parsed, collection_name)
        
        # 4. Check for Advanced Search / Complex Filters / Personnel Queries
        if (getattr(parsed, 'min_students', None) is not None or 
            getattr(parsed, 'max_students', None) is not None or
            getattr(parsed, 'area_name', None) is not None or
            getattr(parsed, 'person_type', None) is not None):
            yield from self._handle_advanced_search(parsed, history)
            return

        # Comparison queries - use SchoolSearchEngine for accurate counts
        if parsed.intent == QueryIntent.COMPARE:
            provinces_found = []
            for province in THAI_PROVINCES:
                if province.lower() in query_lower:
                    provinces_found.append(province)
            
            if len(provinces_found) >= 2:
                # Use SchoolSearchEngine for accurate school counts
                school_engine = SchoolSearchEngine(self.qdrant_client)
                synthesizer = ResponseSynthesizer()
                
                comparison_data = {
                    "query_type": "compare",
                    "provinces": []
                }
                
                for prov in provinces_found:
                    count = school_engine.count_schools(province=prov, agency=parsed.agency)
                    comparison_data["provinces"].append({
                        "province": prov,
                        "count": count
                    })
                
                # Sort by count descending
                comparison_data["provinces"] = sorted(
                    comparison_data["provinces"], 
                    key=lambda x: x['count'], 
                    reverse=True
                )
                
                # Generate response using LLM
                llm_response = synthesizer.synthesize("COMPARE", comparison_data, message)
                
                if llm_response:
                    history[-1]["content"] = llm_response
                else:
                    # Fallback response
                    response_text = "📊 **ผลการเปรียบเทียบจำนวนโรงเรียน**\n\n"
                    for i, p in enumerate(comparison_data["provinces"], 1):
                        response_text += f"{i}. **{p['province']}**: {p['count']:,} โรง\n"
                    
                    if len(comparison_data["provinces"]) >= 2:
                        first = comparison_data["provinces"][0]
                        second = comparison_data["provinces"][1]
                        diff = first['count'] - second['count']
                        if diff > 0:
                            response_text += f"\n✨ **{first['province']}** มีมากกว่า **{second['province']}** อยู่ {diff:,} โรง"
                    
                    history[-1]["content"] = response_text
                
                self.cache.save(message, history[-1]["content"])
                return None  # Already handled
            else:
                collection_name = self.collections.get(parsed.level.value)
                if not collection_name:
                    history[-1]["content"] = f"❌ ไม่พบฐานข้อมูลระดับ {parsed.level.value}"
                    return None
                return self.search_engine.search(parsed, collection_name)
        
        # Normal search
        else:
            collection_name = self.collections.get(parsed.level.value)
            
            if not collection_name or parsed.intent == QueryIntent.UNKNOWN:
                fallback_resp = self._rag_fallback(message)
                history[-1]["content"] = fallback_resp
                self.cache.save(message, fallback_resp)
                return None
            
            # Each region query
            if parsed.region == "each_region":
                parsed.province = None
                parsed.district = None
                parsed.subdistrict = None
                results = self.search_engine.search(parsed, self.collections.get('province'), top_k=200)
            else:
                results = self.search_engine.search(parsed, collection_name)
                
            if not results:
                fallback_resp = self._rag_fallback(message)
                history[-1]["content"] = fallback_resp
                self.cache.save(message, fallback_resp)
                return None
            
            return results

    def _handle_advanced_search(self, parsed: ParsedQuery, message: str, school_engine: SchoolSearchEngine, synthesizer: ResponseSynthesizer, history: List) -> str:
        """Handle comprehensive data queries (students, teachers, area, coordinates, person_type)"""
        
        # --- PERSONNEL TYPE QUERY HANDLING ---
        if parsed.person_type:
            filters = {
                'person_type': parsed.person_type,
                'school_name': parsed.school_name,
                'province': parsed.province
            }
            filters = {k: v for k, v in filters.items() if v is not None}
            
            results = school_engine.search_teachers(filters)
            
            if not results:
                msg = f"เสียดายครับ ไม่พบข้อมูล '{parsed.person_type}' "
                if parsed.school_name: msg += f"ของโรงเรียน {parsed.school_name} ครับ"
                elif parsed.province: msg += f"ในจังหวัด {parsed.province} ครับ"
                else: msg += "ครับ"
                return msg
            
            # Calculate total from 'metadata.count' or 'count'
            total_personnel = 0
            for r in results:
                meta = r.get('metadata', r)  # Handle both nested and flat
                total_personnel += meta.get('count', 0)
            
            # Direct response for specific school
            if parsed.school_name and len(results) > 0:
                meta = results[0].get('metadata', results[0])
                count = meta.get('count', 0)
                return f"โรงเรียน **{parsed.school_name}** มี **{parsed.person_type}** จำนวน **{count}** คนครับ"
            
            # Aggregate response
            msg = f"📊 ข้อมูล **{parsed.person_type}** "
            if parsed.province: msg += f"ในจังหวัด {parsed.province}"
            msg += f"\n\nพบข้อมูลทั้งหมด **{total_personnel:,}** คน (จาก {len(results)} รายการ)"
            return msg
        
        # --- STANDARD SCHOOL SEARCH ---
        # Build filter dict
        filters = {
            'province': parsed.province,
            'district': parsed.district,
            'subdistrict': parsed.subdistrict,
            'agency': parsed.agency,
            'area_name': parsed.area_name,
            'min_students': parsed.min_students,
            'max_students': parsed.max_students,
            'min_teachers': parsed.min_teachers,
            'max_teachers': parsed.max_teachers
        }
        
        # Remove None values
        filters = {k: v for k, v in filters.items() if v is not None}
        
        results, total_count, _ = school_engine.search_by_criteria(filters, limit=15)
        
        data = {
            "query_type": "advanced_search",
            "filters": filters,
            "total": total_count,
            "schools": []
        }
        
        for hit in results:
            meta = hit.payload.get('metadata', {})
            school_data = {
                "name": meta.get('school_name'),
                "province": meta.get('province'),
                "district": meta.get('district'),
                "subdistrict": meta.get('subdistrict'),
                "agency": meta.get('agency'),
                "total_students": meta.get('total_students', 0),
                "total_teachers": meta.get('total_teachers', 0),
                "lat": meta.get('lat'),
                "lon": meta.get('lon'),
                "area_name": meta.get('area_name')
            }
            data["schools"].append(school_data)
            
        llm_response = synthesizer.synthesize("ADVANCED_SEARCH", data, message)
        
        if llm_response:
            response_text = llm_response
        else:
            # Fallback
            criteria_text = []
            if parsed.min_students: criteria_text.append(f"นักเรียน > {parsed.min_students}")
            if parsed.area_name: criteria_text.append(f"สังกัด {parsed.area_name}")
            
            criteria_str = ", ".join(criteria_text)
            response_text = f"🔍 **ผลการค้นหา** ({criteria_str})\n พบทั้งหมด **{total_count:,}** โรงเรียน\n\n"
            
            for i, school in enumerate(data["schools"], 1):
                summ = f"{school['total_students']} คน" if parsed.min_students or parsed.max_students else ""
                response_text += f"{i}. **{school['name']}** {summ}\n"
                
        # Pagination Logic
        if total_count > 15:
            response_text += f"\n\n💡 **พิมพ์ \"ดูเพิ่มเติม\" เพื่อดูต่อ** (เหลืออีก {total_count - 15:,} แห่ง)"
            
            # Save context for Load More
            self.memory.last_school_list_offset = 15
            self.memory.last_school_list_query = {
                'type': 'advanced_criteria', # Marker for advanced search
                'filters': filters,
                'total': total_count
            }
            
        return response_text

    def _aggregate_results(self, results: List, parsed: ParsedQuery, message: str) -> SearchResult:
        """Aggregate search results"""
        is_least = parsed.intent == QueryIntent.RANKING_LEAST
        query_lower = message.lower()
        
        agency_ranking_kw = ['สังกัดไหน', 'สังกัดใด', 'สังกัดอะไร', 'สังกัดที่มี', 
                             'หน่วยงานไหน', 'หน่วยงานใด', 'หน่วยงานอะไร', 'สังกัดการศึกษา']
        is_agency_ranking = (
            parsed.intent in [QueryIntent.RANKING_MOST, QueryIntent.RANKING_LEAST] and
            any(kw in query_lower for kw in agency_ranking_kw)
        )
        
        if is_agency_ranking:
            if parsed.province:
                return self.aggregator.aggregate_by_agency(results, province=parsed.province, is_least=is_least)
            elif parsed.region and parsed.region != "each_region":
                return self.aggregator.aggregate_by_agency(results, region=parsed.region, is_least=is_least)
            else:
                return self.aggregator.aggregate_by_agency(results, is_least=is_least)
        elif parsed.region == "each_region":
            return self.aggregator.aggregate_by_region(results, is_least)
        else:
            return self.aggregator.aggregate(results, parsed.level, is_least)
