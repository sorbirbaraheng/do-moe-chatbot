"""SearchHandlersMixin - Search execution, cache context, and result aggregation."""
import re
import logging
from typing import Dict, List, Optional, Any
from ..core.constants import REGIONS, THAI_PROVINCES, PROVINCE_ALIASES
from ..core.types import ParsedQuery, QueryIntent, QueryLevel, SearchResult
from ..search.query_parser import SmartQueryParser, ResponseSynthesizer
from ..search.school_search import SchoolSearchEngine
logger = logging.getLogger(__name__)

class SearchHandlersMixin:
    """Search dispatch, context strategy, cache key building, and result aggregation."""


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
    def _get_cache_context(self, message: str = ""):
        """Build cache context dict for safe multi-user caching.

        Priority: explicit scope in current message > memory fallback.
        """
        ctx: Dict[str, str] = {}
        msg = (message or "").strip()

        # Normalize Thai numerals for year extraction
        thai_to_arabic = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
        msg_norm = msg.translate(thai_to_arabic)

        # Explicit nationwide scope
        is_country = any(k in msg for k in ["ทั่วประเทศ", "ทั้งประเทศ", "ระดับประเทศ"])
        if is_country:
            ctx["scope"] = "country"

        # Extract explicit region from message
        for region_name in REGIONS.keys():
            if region_name == "ภาคอีสาน":
                continue  # alias; keep canonical region names first
            if region_name in msg:
                ctx["region"] = region_name
                ctx["scope"] = "region"
                break

        # Extract explicit province
        # Prefer deterministic match after keyword "จังหวัด" to avoid false positives.
        province_candidate = None
        if "จังหวัด" in msg:
            tail = msg.split("จังหวัด", 1)[1].strip()
            for prov in sorted(THAI_PROVINCES, key=len, reverse=True):
                if tail.startswith(prov):
                    province_candidate = prov
                    break
            if not province_candidate:
                for alias, full_name in sorted(PROVINCE_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
                    if tail.startswith(alias):
                        province_candidate = full_name
                        break
        else:
            # Fallback: direct province mention in sentence
            for prov in sorted(THAI_PROVINCES, key=len, reverse=True):
                if prov in msg:
                    province_candidate = prov
                    break

        if province_candidate:
            ctx["province"] = province_candidate
            ctx["scope"] = "province"

        # Extract year (supports 25xx or short 2-digit after ปี/พ.ศ.)
        year_match = re.search(r"(?:ปี|พ\.?ศ\.?)\s*(25\d{2}|\d{2})", msg_norm)
        if year_match:
            year_raw = year_match.group(1)
            if len(year_raw) == 2:
                year_raw = f"25{year_raw}"
            ctx["year"] = year_raw

        # If current message is broad scope, avoid leaking narrow scope from memory.
        is_broad_scope_query = any(k in msg for k in ["จังหวัดไหน", "อำเภอไหน", "ภาค", "ทั่วประเทศ", "ระดับประเทศ", "ทั้งประเทศ", "อันดับ"])

        # Memory fallback (only for missing keys)
        if self.memory:
            if not is_broad_scope_query and self.memory.last_district and "district" not in ctx:
                ctx["district"] = self.memory.last_district
                ctx.setdefault("scope", "district")
            if not is_broad_scope_query and self.memory.last_province and "province" not in ctx:
                ctx["province"] = self.memory.last_province
                ctx.setdefault("scope", "province")
            if self.memory.last_region and "region" not in ctx and "province" not in ctx and not is_country:
                ctx["region"] = self.memory.last_region
                ctx.setdefault("scope", "region")
            if self.memory.last_year and "year" not in ctx:
                ctx["year"] = str(self.memory.last_year)
            if hasattr(self.memory, 'last_school_name') and self.memory.last_school_name and "school_name" not in ctx:
                ctx["school_name"] = str(self.memory.last_school_name)

        return ctx or None
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

        # Comparison queries - detect metric and use correct data source
        if parsed.intent == QueryIntent.COMPARE:
            provinces_found = []
            for province in THAI_PROVINCES:
                if province.lower() in query_lower:
                    provinces_found.append(province)
            
            if len(provinces_found) >= 2:
                # Detect what metric is being compared
                is_student_compare = any(kw in query_lower for kw in ["นักเรียน", "เด็ก", "ผู้เรียน"])
                is_teacher_compare = any(kw in query_lower for kw in ["ครู", "บุคลากร", "อาจารย์"])
                synthesizer = ResponseSynthesizer()

                comparison_data = {
                    "query_type": "compare",
                    "metric": "students" if is_student_compare else ("teachers" if is_teacher_compare else "schools"),
                    "provinces": []
                }

                for prov in provinces_found:
                    try:
                        if is_student_compare:
                            result = self.llm_agent.tool_executor._count_students(
                                province=prov, school_name=None, region=None, district=None,
                                grade=None, gender=None, year=getattr(parsed, 'year', None)
                            )
                            count = result.get("total_count", 0) if isinstance(result, dict) else 0
                        elif is_teacher_compare:
                            result = self.llm_agent.tool_executor._count_teachers(
                                province=prov, school_name=None, region=None, district=None,
                                gender=None, person_type=None, year=getattr(parsed, 'year', None)
                            )
                            count = result.get("total_count", 0) if isinstance(result, dict) else 0
                        else:
                            school_engine = SchoolSearchEngine(self.qdrant_client)
                            count = school_engine.count_schools(province=prov, agency=parsed.agency)
                    except Exception as _ce:
                        logger.warning(f"⚠️ Comparison count error for {prov}: {_ce}")
                        count = 0

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

                # Metric label
                metric_label = "นักเรียน" if is_student_compare else ("ครู" if is_teacher_compare else "โรงเรียน")
                unit = "คน" if (is_student_compare or is_teacher_compare) else "แห่ง"

                # If all counts are 0, data retrieval failed — skip and let LLM agent handle
                if all(p["count"] == 0 for p in comparison_data["provinces"]):
                    logger.warning(f"⚠️ All comparison counts are 0, skipping comparison path")
                    # Fall through to LLM agent path below
                else:
                    # Build formatted response directly (skip LLM synthesizer which is unreliable for comparison)
                    provinces_sorted = comparison_data["provinces"]
                    first = provinces_sorted[0]
                    second = provinces_sorted[1] if len(provinces_sorted) >= 2 else None

                    response_text = f"📊 **เปรียบเทียบจำนวน{metric_label}**\n\n"
                    response_text += f"| จังหวัด | จำนวน{metric_label} |\n|--------|-------:|\n"
                    for p in provinces_sorted:
                        response_text += f"| **{p['province']}** | {p['count']:,} {unit} |\n"

                    if second and first["count"] > 0:
                        diff = first["count"] - second["count"]
                        pct = round(diff / second["count"] * 100, 1) if second["count"] > 0 else 0
                        if diff > 0:
                            response_text += f"\n✨ **{first['province']}** มีมากกว่า **{second['province']}** อยู่ **{diff:,} {unit}** ({pct}%) ครับ"
                        else:
                            response_text += f"\n🔁 จำนวน{metric_label}ใกล้เคียงกันครับ"

                    history[-1]["content"] = response_text
                    self.cache.save(message, history[-1]["content"], context=self._get_cache_context())
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
                self.cache.save(message, fallback_resp, context=self._get_cache_context())
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
                self.cache.save(message, fallback_resp, context=self._get_cache_context())
                return None
            
            return results
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
