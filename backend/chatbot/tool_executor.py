"""
🔧 Tool Executor
Executes tool calls by querying Qdrant and returning structured data.
"""

import logging
import difflib
from typing import Dict, Any, List, Optional, Tuple, Union
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchText, MatchAny, Range
from .school_search import SchoolSearchEngine
from .constants import (
    COLLECTION_NAMES,
    THAI_PROVINCES,
    REGIONS,
    YEAR_COLLECTIONS,
    YEAR_ALIASES,
    AVAILABLE_YEARS,
)

logger = logging.getLogger(__name__)

class ToolExecutor:
    """
    Executes education chatbot tools against Qdrant database.
    Each tool returns structured data that LLM can use to generate responses.
    """
    
    def __init__(self, qdrant_client: QdrantClient, llm_provider=None):
        self.client = qdrant_client
        self.llm_provider = llm_provider
        
        # Use centralized collection names from constants
        # from .constants import COLLECTION_NAMES (Moved to top)
        self.collections = COLLECTION_NAMES.copy()
        
        # Active year for collection routing (set per-request in execute())
        self._active_year = None
        
        # Initialize specialized search engine
        self.search_engine = SchoolSearchEngine(self.client, llm_provider=llm_provider)
    
    def _get_collection(self, key: str, year: str = None) -> str:
        """Get collection name based on year. Uses _active_year if year not specified."""
        y = year or self._active_year
        if y and y in YEAR_COLLECTIONS:
            return YEAR_COLLECTIONS[y].get(key, self.collections.get(key, ""))
        return self.collections.get(key, "")
    
    def _normalize_year(self, year: str = None) -> str:
        """Normalize year value (e.g. '67' -> '2567')"""
        if not year:
            return None
        year = str(year).strip()
        if year in YEAR_ALIASES:
            return YEAR_ALIASES[year]
        return year
    
    def execute(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return structured data"""
        logger.info(f"🔧 Executing tool: {tool_name} with params: {params}")
        
        # Extract and normalize year for collection routing
        raw_year = params.get("year")
        self._active_year = self._normalize_year(raw_year)
        if raw_year and self._active_year not in AVAILABLE_YEARS:
            return {
                "tool": tool_name,
                "error": f"ไม่มีข้อมูลปี {self._active_year} ในระบบ",
                "available_years": AVAILABLE_YEARS,
            }
        if self._active_year:
            logger.info(f"📅 Year-based routing active: {self._active_year}")
        
        try:
            if tool_name == "search_schools":
                return self._search_schools(**params)
            elif tool_name == "count_teachers":
                return self._count_teachers(**params)
            elif tool_name == "count_students":
                return self._count_students(**params)
            elif tool_name == "count_schools":
                return self._count_schools(**params)
            elif tool_name == "get_ratio":
                return self._get_ratio(**params)
            elif tool_name == "compare":
                return self._compare(**params)
            elif tool_name == "ranking":
                return self._ranking(**params)
            elif tool_name == "list_schools":
                return self._list_schools(**params)
            elif tool_name == "filter_schools":
                return self._filter_schools(**params)
            # Phase 1: New tools
            elif tool_name == "search_education_areas":
                return self._search_education_areas(**params)
            elif tool_name == "get_education_area_info":
                return self._get_education_area_info(**params)
            elif tool_name == "get_school_full_details":
                if not params.get("school_name"):
                    return {
                        "tool": "get_school_full_details",
                        "error": "School name is required"
                    }
                return self._get_school_full_details(**params)
            elif tool_name == "get_province_summary":
                return self._get_province_summary(**params)
            # Phase 2: New tools
            elif tool_name == "count_by_system_type":
                return self._count_by_system_type(**params)
            elif tool_name == "analyze_gender_ratio":
                return self._analyze_gender_ratio(**params)
            elif tool_name == "get_grade_distribution":
                return self._get_grade_distribution(**params)
            elif tool_name == "find_best_ratio_schools":
                return self._find_best_ratio_schools(**params)
            # Phase 3: New tools
            elif tool_name == "analyze_teacher_distribution":
                return self._analyze_teacher_distribution(**params)
            elif tool_name == "ranking_by_agency":
                return self._ranking_by_agency(**params)
            elif tool_name == "ranking_subdistricts":
                return self._ranking_subdistricts(**params)
            elif tool_name == "get_district_summary":
                return self._get_district_summary(**params)
            elif tool_name == "compare_provinces":
                return self._compare_provinces(**params)
            elif tool_name == "compare_years":
                return self._compare_years(**params)
            elif tool_name == "find_nearby_schools":
                return self._find_nearby_schools(**params)
            elif tool_name == "general_chat":
                # Returns a special marker to tell the LLM to answer using its own knowledge/RAG
                return {"type": "general_knowledge", "info": "Please answer this question using your general knowledge or RAG context."}
            elif tool_name == "advanced_school_search":
                return self._advanced_school_search(**params)
            elif tool_name == "advanced_school_search":
                return self._advanced_school_search(**params)
            elif tool_name == "filter_schools":
                return self._filter_schools(**params)
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            logger.error(f"❌ Tool execution error: {e}")
            return {"error": str(e)}
    
    def _build_filter(self, conditions: List[FieldCondition]) -> Optional[Filter]:
        """Build a Qdrant filter from conditions (supports nested Filter in list)."""
        if not conditions:
            return None

        must: List[Any] = []
        should: List[Any] = []
        must_not: List[Any] = []

        for cond in conditions:
            if isinstance(cond, Filter):
                # Flatten nested filter to avoid must=[Filter(...)] issues
                if cond.must:
                    must.extend(cond.must)
                if cond.should:
                    should.extend(cond.should)
                if cond.must_not:
                    must_not.extend(cond.must_not)
            else:
                must.append(cond)

        if not must and not should and not must_not:
            return None

        return Filter(
            must=must or None,
            should=should or None,
            must_not=must_not or None,
        )
    
    def _scroll_all(self, collection: str, scroll_filter: Optional[Filter], limit: int = 1000, with_payload: Union[bool, List[str]] = True) -> List:
        """Scroll through all matching records"""
        all_results = []
        offset = None
        
        while len(all_results) < limit:
            response = self.client.scroll(
                collection_name=collection,
                scroll_filter=scroll_filter,
                limit=min(500, limit - len(all_results)),
                offset=offset,
                with_payload=with_payload
            )
            
            points = response[0]
            next_offset = response[1]
            
            all_results.extend(points)
            
            if next_offset is None or len(points) == 0:
                break
            offset = next_offset
        
        return all_results
    
    def _count_filtered(self, collection: str, count_filter: Optional[Filter]) -> int:
        """Count matching records without fetching them"""
        try:
            result = self.client.count(
                collection_name=collection,
                count_filter=count_filter,
                exact=True
            )
            return result.count
        except Exception as e:
            logger.warning(f"Count query failed: {e}, falling back to scroll count")
            # Fallback: do a scroll with high limit and count results
            return len(self._scroll_all(collection, count_filter, limit=10000))
    
    # ============================================================
    # HELPER METHODS
    # ============================================================

    def _thai_to_arabic_numerals(self, text: str) -> str:
        """Convert Thai numerals to Arabic (๐๑๒๓๔๕๖๗๘๙ → 0123456789)"""
        if not text:
            return text
        thai_numerals = "๐๑๒๓๔๕๖๗๘๙"
        arabic_numerals = "0123456789"
        for thai, arabic in zip(thai_numerals, arabic_numerals):
            text = text.replace(thai, arabic)
        return text

    def _normalize_province(self, province: str) -> str:
        """Normalize province name with aliases"""
        if not province:
            return province
        province = province.replace("จ.", "").replace("จังหวัด", "").strip()
        
        # Bangkok aliases
        bangkok_aliases = ["กทม", "กทม.", "กรุงเทพ", "กรุงเทพฯ", "bkk"]
        if province.lower() in [a.lower() for a in bangkok_aliases]:
            return "กรุงเทพมหานคร"
        
        return province

    def _normalize_agency(self, agency: str) -> str:
        """Normalize agency abbreviations to full names"""
        if not agency:
            return agency
        
        agency_mapping = {
            "สพฐ": "สำนักงานคณะกรรมการการศึกษาขั้นพื้นฐาน",
            "สพฐ.": "สำนักงานคณะกรรมการการศึกษาขั้นพื้นฐาน",
            "สช": "สำนักงานคณะกรรมการส่งเสริมการศึกษาเอกชน",
            "สช.": "สำนักงานคณะกรรมการส่งเสริมการศึกษาเอกชน",
            "เอกชน": "สำนักงานคณะกรรมการส่งเสริมการศึกษาเอกชน",
            "อาชีวะ": "สำนักงานคณะกรรมการการอาชีวศึกษา",
            "สอศ": "สำนักงานคณะกรรมการการอาชีวศึกษา",
            "สอศ.": "สำนักงานคณะกรรมการการอาชีวศึกษา",
            "กทม": "กรุงเทพมหานคร",
            "กทม.": "กรุงเทพมหานคร",
            "ท้องถิ่น": "กรมส่งเสริมการปกครองท้องถิ่น",
            "อปท": "กรมส่งเสริมการปกครองท้องถิ่น",
            "อปท.": "กรมส่งเสริมการปกครองท้องถิ่น",
            "ตชด": "กองบัญชาการตำรวจตระเวนชายแดน",
            "ตชด.": "กองบัญชาการตำรวจตระเวนชายแดน",
        }
        
        agency_clean = agency.strip()
        return agency_mapping.get(agency_clean, agency)

    def _normalize_person_type(self, person_type: str) -> str:
        """Normalize person_type aliases to match Qdrant values"""
        if not person_type:
            return person_type
        
        # Map common aliases to actual values in Qdrant
        person_type_mapping = {
            # ครูอัตราจ้าง variants
            "ครูอัตราจ้าง": "ลูกจ้างชั่วคราว",
            "อัตราจ้าง": "ลูกจ้างชั่วคราว",
            "ครูจ้าง": "ลูกจ้างชั่วคราว",
            # ข้าราชการครู variants
            "ครู": "ข้าราชการครู",
            "ข้าราชการ": "ข้าราชการครู",
            # พนักงานราชการ variants
            "พนง.ราชการ": "พนักงานราชการ",
            "พนง.": "พนักงานราชการ",
            # ลูกจ้าง variants
            "ลูกจ้าง": "ลูกจ้างชั่วคราว",
            "ลจ.": "ลูกจ้างชั่วคราว",
            "ลูกจ้างประจำ": "ลูกจ้างประจำ",  # Keep as-is
            # บุคลากร variants
            "บุคลากร": "บุคลากรทางการศึกษา",
        }
        
        pt_clean = person_type.strip()
        return person_type_mapping.get(pt_clean, pt_clean)

    def _normalize_grade(self, grade: str) -> str:
        """Normalize grade level name (e.g. ป.1 -> ประถมศึกษาปีที่ 1)"""
        if not grade:
            return grade
            
        grade = grade.strip()
        
        # Remove common prefixes
        for prefix in ["ชั้น", "ระดับชั้น", "ระดับ"]:
            if grade.startswith(prefix):
                grade = grade[len(prefix):].strip()
        
        mapping = {
            # อนุบาล (Support variants)
            "อ.1": "อนุบาล 1", "อ.2": "อนุบาล 2", "อ.3": "อนุบาล 3",
            "อนุบาล1": "อนุบาล 1", "อนุบาล2": "อนุบาล 2", "อนุบาล3": "อนุบาล 3",
            "อ1": "อนุบาล 1", "อ2": "อนุบาล 2", "อ3": "อนุบาล 3",
            
            # ประถมศึกษา (Support no-dot)
            "ป.1": "ประถมศึกษาปีที่ 1", "ป.2": "ประถมศึกษาปีที่ 2", "ป.3": "ประถมศึกษาปีที่ 3",
            "ป.4": "ประถมศึกษาปีที่ 4", "ป.5": "ประถมศึกษาปีที่ 5", "ป.6": "ประถมศึกษาปีที่ 6",
            "ป1": "ประถมศึกษาปีที่ 1", "ป2": "ประถมศึกษาปีที่ 2", "ป3": "ประถมศึกษาปีที่ 3",
            "ป4": "ประถมศึกษาปีที่ 4", "ป5": "ประถมศึกษาปีที่ 5", "ป6": "ประถมศึกษาปีที่ 6",
            
            # มัธยมศึกษา (Support no-dot)
            "ม.1": "มัธยมศึกษาปีที่ 1", "ม.2": "มัธยมศึกษาปีที่ 2", "ม.3": "มัธยมศึกษาปีที่ 3",
            "ม.4": "มัธยมศึกษาปีที่ 4", "ม.5": "มัธยมศึกษาปีที่ 5", "ม.6": "มัธยมศึกษาปีที่ 6",
            "ม1": "มัธยมศึกษาปีที่ 1", "ม2": "มัธยมศึกษาปีที่ 2", "ม3": "มัธยมศึกษาปีที่ 3",
            "ม4": "มัธยมศึกษาปีที่ 4", "ม5": "มัธยมศึกษาปีที่ 5", "ม6": "มัธยมศึกษาปีที่ 6", 
            
            # อาชีวศึกษา - ปวช. (Exact match from Qdrant)
            "ปวช.1": "ประกาศนียบัตรวิชาชีพปีที่ 1", "ปวช.2": "ประกาศนียบัตรวิชาชีพปีที่ 2", 
            "ปวช.3": "ประกาศนียบัตรวิชาชีพปีที่ 3",
            "ปวช1": "ประกาศนียบัตรวิชาชีพปีที่ 1", "ปวช2": "ประกาศนียบัตรวิชาชีพปีที่ 2",
            "ปวช3": "ประกาศนียบัตรวิชาชีพปีที่ 3",
            # อาชีวศึกษา - ปวส. (Fixed: Added 'ชั้น' before 'ปีที่')
            "ปวส.1": "ประกาศนียบัตรวิชาชีพชั้นสูงชั้นปีที่ 1", "ปวส.2": "ประกาศนียบัตรวิชาชีพชั้นสูงชั้นปีที่ 2",
            "ปวส1": "ประกาศนียบัตรวิชาชีพชั้นสูงชั้นปีที่ 1", "ปวส2": "ประกาศนียบัตรวิชาชีพชั้นสูงชั้นปีที่ 2",
        }
        
        for k, v in mapping.items():
            if k in grade or grade == k:
                # print(f"DEBUG: Normalized '{grade}' with key '{k}' -> '{v}'")
                return v
        print(f"DEBUG: Failed to normalize '{grade}'. Available keys snippet: {list(mapping.keys())[-5:]}")
        print(f"DEBUG: Failed to normalize '{grade}'. Available keys snippet: {list(mapping.keys())[-5:]}")
        return grade

    def _normalize_region(self, region: str) -> Optional[str]:
        """Normalize region name (e.g. อีสาน -> ภาคตะวันออกเฉียงเหนือ)"""
        if not region: return None
        
        from .constants import REGIONS
        
        region = region.strip()
        if region in REGIONS:
            return region
            
        # Common aliases
        aliases = {
            "เหนือ": "ภาคเหนือ",
            "อีสาน": "ภาคตะวันออกเฉียงเหนือ",
            "ตะวันออกเฉียงเหนือ": "ภาคตะวันออกเฉียงเหนือ",
            "กลาง": "ภาคกลาง",
            "ตะวันออก": "ภาคตะวันออก",
            "ตะวันตก": "ภาคตะวันตก",
            "ใต้": "ภาคใต้",
        }
        
        # Try exact alias
        if region in aliases:
            return aliases[region]
            
        # Try partial match (e.g. "ภาคอีสาน")
        for k, v in aliases.items():
            if k in region:
                return v
                
        return None

    def _get_region_data(self, region: str, metric: str) -> Dict[str, Any]:
        """Aggregate data for a whole region"""
        from .constants import REGIONS
        
        provinces = REGIONS.get(region, [])
        if not provinces:
            return {"error": f"Region {region} not found"}
            
        logger.info(f"🌍 Aggregating data for region '{region}' ({len(provinces)} provinces)")
        
        # Prepare MatchAny filter for all provinces in the region
        province_filter = Filter(
            must=[
                FieldCondition(
                    key="metadata.province", 
                    match=MatchAny(any=provinces)
                )
            ]
        )
        
        total = 0
        details = {}
        
        if metric == "schools":
            # Count schools in region
            total = self._count_filtered(self._get_collection("schools"), province_filter)
            details = {"province_count": len(provinces)}
            
        elif metric == "students":
            # Count students in region
            # Optimization: Use SCHOOLS collection sum if possible, but for accuracy use STUDENTS collection
            # Using SCHOOLS collection is faster for big aggregations
            # OPTIMIZATION: Only fetch total_students field
            schools_res = self._scroll_all(self._get_collection("schools"), province_filter, limit=50000, 
                                          with_payload=["metadata.total_students"])
            total = sum(r.payload.get("metadata", {}).get("total_students", 0) for r in schools_res)
            details = {"source": "schools_aggregation"}
            
        elif metric == "teachers":
            # Count teachers in region
            # OPTIMIZATION: Only fetch total_teachers field
            schools_res = self._scroll_all(self._get_collection("schools"), province_filter, limit=50000,
                                          with_payload=["metadata.total_teachers"])
            total = sum(r.payload.get("metadata", {}).get("total_teachers", 0) for r in schools_res)
            details = {"source": "schools_aggregation"}
            
        elif metric == "ratio":
             # Optimization: Fetch ONLY totals for calculation
             # We need sum of student and sum of teachers
             students_res = self._scroll_all(self._get_collection("schools"), province_filter, limit=50000,
                                            with_payload=["metadata.total_students"])
             teachers_res = self._scroll_all(self._get_collection("schools"), province_filter, limit=50000,
                                            with_payload=["metadata.total_teachers"])
             
             total_s = sum(r.payload.get("metadata", {}).get("total_students", 0) for r in students_res)
             total_t = sum(r.payload.get("metadata", {}).get("total_teachers", 0) for r in teachers_res)
             
             details = {
                 "total_students": total_s,
                 "total_teachers": total_t,
                 "source": "schools_aggregation"
             }
             total = round(total_s / total_t, 2) if total_t > 0 else 0

        return {
            "name": region,
            "type": "region",
            "total": total,
            "metric": metric,
            "details": details
        }

    def _clean_search_query(self, query: str) -> str:
        """Clean search query by removing common question words/particles"""
        if not query: return query
        
        # Common suffixes to remove
        remove_words = [
            "อยู่ที่ไหน", "ตั้งอยู่ที่ไหน", "อยู่ตรงไหน", "อยู่ไหน", 
            "ไปทางไหน", "ไปยังไง", "แผนที่", "พิกัด", "ตำแหน่ง",
            "มีกี่แห่ง", "มีกี่โรงเรียน", "คืออะไร",
            "มีที่ไหนบ้าง", "ที่ไหนบ้าง", "มีที่ไหน", "ที่ไหน", "ที่ใด",
            "มีกี่ที่", "มีไหม", "บ้าง", "ทั้งหมด",
            "ครับ", "ค่ะ", "จ้ะ", "จ้า", "นะ", "นะคะ"
        ]
        
        clean = query
        for word in remove_words:
            clean = clean.replace(word, "")
            
        return clean.strip()
        
    def _resolve_school_ambiguity(self, school_name: str, province: str = None, district: str = None) -> Dict[str, Any]:
        """
        Helper to check if a school name implies multiple matches.
        Returns: 
           - {'type': 'single', 'data': school_obj}
           - {'type': 'ambiguous', 'choices': [list of schools]}
           - {'type': 'not_found'}
        """
        # Search with a reasonable limit to catch duplicates
        matches = self._smart_search_school(school_name, province, limit=20)
        
        # FALLBACK: If not found in the specific province, try GLOBAL search
        if not matches and province:
             logger.info(f"🔄 Disambiguation: '{school_name}' not found in '{province}', trying global search...")
             matches = self._smart_search_school(school_name, province=None, limit=20)
        
        if not matches:
            return {'type': 'not_found'}
            
        # Filter strictly by name similarity to avoid loose fuzzy matches triggering disambiguation unnecessarily
        clean_input = self._clean_search_query(school_name).replace("โรงเรียน", "").strip()
        
        # If district is specified, filter matches by district first
        if district:
            district_clean = district.replace("เขต", "").replace("อำเภอ", "").strip()
            filtered = [m for m in matches 
                       if district_clean in (m.payload.get('metadata', {}).get('district', '') or '')]
            if filtered:
                matches = filtered
                logger.info(f"📋 District filter '{district_clean}' narrowed to {len(matches)} matches")
        
        unique_names = {}
        for m in matches:
            meta = m.payload.get('metadata', {})
            name = meta.get('school_name', '')
            dist = meta.get('district', '')
            prov = meta.get('province', '')
            key = f"{name}_{prov}"
            if key not in unique_names:
                unique_names[key] = {
                    "school_name": name,
                    "district": dist,
                    "province": prov,
                    "school_id": meta.get('school_id'),
                    "total_students": meta.get('total_students', 0), # Enrich metrics
                    "total_teachers": meta.get('total_teachers', 0)  # Enrich metrics
                }
        
        unique_list = list(unique_names.values())
        
        if len(unique_list) == 1:
            return {'type': 'single', 'data': matches[0]}
            
        # If multiple matches...
        return {'type': 'ambiguous', 'choices': unique_list}

    # ============================================================
    # TOOL IMPLEMENTATIONS
    # ============================================================
    
    def _smart_search_school(self, school_name: str, province: str = None, limit: int = 5) -> List[Any]:
        """Hybrid search strategy: Exact -> Prefix -> Fuzzy"""
        results = []
        found_ids = set()
        
        # Determine query variations
        queries_to_try = []
        if school_name:
            # 0. Strip question words first!
            cleaned_school_name = self._clean_search_query(school_name)
            logger.info(f"🧹 Query Cleaning: '{school_name}' -> '{cleaned_school_name}'")
            school_name = cleaned_school_name
            
            school_name = self._thai_to_arabic_numerals(school_name)
            clean_name = school_name.replace("ร.ร.", "").replace("รร.", "").replace("รร", "").replace("โรงเรียน", "").strip()
            
            # 1. Clean name first (most likely to match)
            queries_to_try.append(clean_name)
            
            # 2. Original input (if different from clean)
            if school_name != clean_name and school_name not in queries_to_try:
                queries_to_try.append(school_name)
            
            # 3. "โรงเรียน" + clean_name
            queries_to_try.append(f"โรงเรียน{clean_name}")
            
            # 4. clean_name + Suffixes (For short names like "สวนกุหลาบ" -> "สวนกุหลาบวิทยาลัย")
            suffixes = ["วิทยาลัย", "ศึกษา", "วิทยา", "พัฒนาการ"]
            for suffix in suffixes:
                if not clean_name.endswith(suffix):
                    queries_to_try.append(f"{clean_name}{suffix}")
                    
            # ⚡ PRIORITY 0: Exact Match on Processed Name (The "Pattani" Fix)
            # This ensures "โรงเรียนเมืองปัตตานี" -> "เมืองปัตตานี" -> MatchValue("เมืองปัตตานี") -> FOUND
            queries_to_try.insert(0, {"type": "exact", "value": clean_name})
            
        else:
            queries_to_try = [None]
            
        logger.info(f"🔍 Smart Search Pattern: {queries_to_try}")

        for query in queries_to_try:
            if len(results) >= limit:
                break
                
            conditions = []
            if query:
                if isinstance(query, dict) and query.get("type") == "exact":
                    # Exact Match Strategy (High Precision)
                    conditions.append(FieldCondition(key="metadata.school_name", match=MatchValue(value=query["value"])))
                else:
                    # Fuzzy/Text Match Strategy (Standard)
                    conditions.append(FieldCondition(key="metadata.school_name", match=MatchText(text=query)))
            if province:
                p_norm = self._normalize_province(province)
                conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=p_norm)))
                
            scroll_filter = self._build_filter(conditions)
            batch = self._scroll_all(self._get_collection("schools"), scroll_filter, limit=limit)
            
            for res in batch:
                sid = res.payload.get('metadata', {}).get('school_id')
                if sid and sid not in found_ids:
                    results.append(res)
                    found_ids.add(sid)

        # 5. Fallback: Semantic/Vector Search (if exact matches failed or insufficient)
        if len(results) < limit:
            logger.info("⚠️ Exact match insufficient, falling back to Semantic Search...")
            try:
                # Import here to avoid circular dependency if possible, or use global
                from .search_engine import SearchEngine
                
                # We need to instantiate SearchEngine on the fly or reuse one if available
                # Since ToolExecutor has QdrantClient, we can pass it
                engine = SearchEngine(self.client, llm_provider=self.llm_provider)
                
                # Use the original school name (concept) for semantic search
                # We reuse the province filter if it exists
                # _semantic_search handles embedding generation internally via the LLM/Embedder
                
                # IMPORTANT: We need to build the filter properly for the search engine
                semantic_filter = None
                if province:
                    p_norm = self._normalize_province(province)
                    semantic_filter = Filter(must=[
                        FieldCondition(key="metadata.province", match=MatchValue(value=p_norm))
                    ])
                
                # Perform vector search
                # Note: We use original_school_name passed to _search_schools if available, 
                # but here we only have 'school_name' arg. 
                # In _search_schools, we passed 'original_school_name' to this function.
                semantic_results = engine._semantic_search(
                    query=school_name, 
                    collection_name=self._get_collection("schools"),
                    top_k=limit - len(results),
                    filters=semantic_filter
                )
                
                if semantic_results:
                    logger.info(f"🧠 Semantic Search found {len(semantic_results)} results")
                    for res in semantic_results:
                        # Filter out low confidence matches
                        if res.score < 0.65: 
                            continue
                            
                        sid = res.payload.get('metadata', {}).get('school_id')
                        if sid and sid not in found_ids:
                            results.append(res)
                            found_ids.add(sid)
            except Exception as e:
                logger.error(f"❌ Semantic search fallback failed: {e}")
                
        return results

    def _suggest_schools(self, school_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Find similar school names when exact search fails"""
        if not school_name:
            return []
            
        suggestions = []
        seen = set()
        
        # 1. Broad text search on school name field
        clean_name = self._thai_to_arabic_numerals(school_name)
        clean_name = clean_name.replace("โรงเรียน", "").replace("รร.", "").strip()
        
        if len(clean_name) < 2: 
            return []

        # Strategy 1: First word (Token match)
        keywords = clean_name.split()
        search_terms = []
        if keywords:
            search_terms.append(keywords[0])
            
        # Strategy 2: Prefix (Robust against suffix typos)
        if len(clean_name) > 4:
            search_terms.append(clean_name[:4]) # First 4 chars often identify the school (e.g. "เตรียม")
        
        # Strategy 3: Aggressive Fuzzy (First 2-3 chars) - Fallback for typos like "อะมานะ"
        if len(clean_name) >= 3:
             search_terms.append(clean_name[:2]) if len(clean_name) < 5 else search_terms.append(clean_name[:3])
        
        for term in search_terms:
            if len(suggestions) >= limit: break
            
            condition = FieldCondition(key="metadata.school_name", match=MatchText(text=term))
            results = self._scroll_all(self._get_collection("schools"), self._build_filter([condition]), limit=20)
            
            for r in results:
                meta = r.payload.get("metadata", {})
                name = meta.get("school_name", "")
                if name and name not in seen:
                    seen.add(name)
                    suggestions.append({
                        "name": name,
                        "province": meta.get("province"),
                        "school_id": meta.get("school_id")
                    })
                    if len(suggestions) >= limit:
                        break
        
        return suggestions

    def _search_schools(self, school_name: str = None, province: str = None, 
                        district: str = None, subdistrict: str = None, agency: str = None, region: str = None,
                        metric: str = None, limit: int = 10, **kwargs) -> Dict[str, Any]:
        """Search for schools with various filters, supporting extra params like grade"""
        
        # If 'grade' is passed/extracted (e.g. "อนุบาล") but no school name, 
        # use it as the search term for semantic search.
        grade_param = kwargs.get('grade')
        if not school_name and grade_param:
            logger.info(f"💡 Using extracted grade '{grade_param}' as school_name for semantic search")
            school_name = grade_param

        original_school_name = school_name  # Save for fuzzy search fallback
        actual_total_count = 0  # Track actual total count (not limited)
        
        # Build filter for counting (need to build it for both paths)
        count_conditions = []
        if school_name:
            # Only clean if it looks like a specific school name, not a generic concept
            # For concepts like "อนุบาล", we want to keep them for semantic search
            clean_name = self._thai_to_arabic_numerals(school_name)
            if "โรงเรียน" in clean_name or "รร" in clean_name:
                clean_name = clean_name.replace("ร.ร.", "").replace("รร.", "").replace("รร", "").replace("โรงเรียน", "").strip()
            
            # Note: We don't filter by name strictly here if we want semantic search to work
            # But for exact counting, we might need to. 
            # For V6 switch-over, let's rely on smart search for the main retrieval.
            pass 

        if province:
            count_conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=self._normalize_province(province))))
        
        # Region Filter (New Feature)
        if region and not province: # Province takes precedence
            target_provinces = REGIONS.get(region, [])
            if target_provinces:
                logger.info(f"📍 Filtering by Region: {region} -> {len(target_provinces)} provinces")
                count_conditions.append(FieldCondition(key="metadata.province", match=MatchAny(any=target_provinces)))
            else:
                logger.warning(f"⚠️ Region '{region}' not found or empty")
        if district:
            # Normalize district by removing common prefixes
            district_clean = district.replace('อำเภอ', '').replace('อ.', '').replace('เขต', '').strip()
            # Use MatchText which should match "พญาไท" against "เขตพญาไท" or "พญาไท"
            count_conditions.append(FieldCondition(key="metadata.district", match=MatchText(text=district_clean)))
        if agency:
            count_conditions.append(FieldCondition(key="metadata.agency", match=MatchText(text=self._normalize_agency(agency))))
        if subdistrict:
            count_conditions.append(FieldCondition(key="metadata.subdistrict", match=MatchText(text=subdistrict)))
        
        # Get actual total count first (before limiting)
        if count_conditions:
            count_filter = self._build_filter(count_conditions)
            actual_total_count = self._count_filtered(self._get_collection("schools"), count_filter)
        else:
            # No filters = count all schools
            actual_total_count = self._count_filtered(self._get_collection("schools"), None)
        
        if actual_total_count == 0:
             # Smart Fallback: If filtered by location but found nothing, try fuzzy suggestion
             if subdistrict or district:
                 suggestion = self._get_fuzzy_suggestion(subdistrict, province, district)
                 if suggestion:
                     return {"tool": "search_schools", "found": False, "total_found": 0, "results": [], "ai_summary": suggestion}
             
             return {"tool": "search_schools", "found": False, "total_found": 0, "results": []}

        # Use SchoolSearchEngine for consistent results
        # If school_name is present, user intends to find specific schools, so strict/fuzzy count matters more than DB count
        if school_name and not district and not agency:
             # Strategy: Fetch more results to determine if we have more than the limit
             # If user asks for 10, we fetch 50 to see if there are 11-50 matches
             fetch_limit = 50 
             results = self._smart_search_school(original_school_name, province, limit=fetch_limit)
             
             # Adjust actual_total_count based on what we ACTUALLY found
             # Since _smart_search_school returns unique matches for the name
             actual_total_count = len(results)
             
             # Now apply the user's limit for display
             if len(results) > int(limit):
                 results = results[:int(limit)]
                 # If we hit the fetch_limit (50), we should probably say "50+" or rely on this being enough for "Where are they?" queries
                 if actual_total_count >= fetch_limit:
                     actual_total_count = f"{fetch_limit}+" # Indicator that there are many

        else:
             # Use filters
             results = self._scroll_all(self._get_collection("schools"), count_filter if count_conditions else None, limit=int(limit))
             
        # Format results
        formatted = []
        for r in results:
             meta = r.payload.get("metadata", {}) if hasattr(r, "payload") else r
             item = {
                "school_name": meta.get("school_name"),
                "province": meta.get("province"),
                "district": meta.get("district"),
                "total_students": meta.get("total_students"),
                "total_teachers": meta.get("total_teachers"),
                "agency": meta.get("agency")
             }
             
             # Smart Column Pruning (Data Cleaning)
             # Case 1: Specific Metric Requested
             if metric == "students":
                 # User wants students -> Hide teachers (but keep students even if 0)
                 if "total_teachers" in item: del item["total_teachers"]
             elif metric == "teachers":
                 # User wants teachers -> Hide students (but keep teachers even if 0)
                 if "total_students" in item: del item["total_students"]
             
             formatted.append(item)
        
        # Case 2: Auto-Hide Empty Columns (only if NO specific metric requested)
        if not metric and formatted:
            # Check if all items have 0/None for students
            all_no_students = all(not item.get("total_students") for item in formatted)
            # Check if all items have 0/None for teachers
            all_no_teachers = all(not item.get("total_teachers") for item in formatted)
            
            if all_no_students or all_no_teachers:
                logger.info(f"🧹 Auto-Pruning: Students={all_no_students}, Teachers={all_no_teachers}")
                for item in formatted:
                    if all_no_students and "total_students" in item:
                        del item["total_students"]
                    if all_no_teachers and "total_teachers" in item:
                        del item["total_teachers"]
             
        # Note: actual_total_count is already adjusted for name-based searches above.

        # SUGGESTION LOGIC: If no results found, try to find similar schools
        suggestions = []
        if len(formatted) == 0 and original_school_name:
             logger.info(f"🤔 No results for '{original_school_name}', trying suggestions...")
             suggestions = self._suggest_schools(original_school_name)
             
        # AI Summary to prevent hallucination
        ai_summary = f"พบโรงเรียนทั้งหมด {actual_total_count} แห่ง แต่แสดงผลเพียง {len(formatted)} แห่ง"
        if actual_total_count == len(formatted):
             ai_summary = f"พบโรงเรียนทั้งหมด {actual_total_count} แห่ง (แสดงครบแล้ว)"

        return {
            "tool": "search_schools",
            "found": len(formatted) > 0,
            "total_found": actual_total_count, 
            "results": formatted,
            "suggestions": suggestions,
            "ai_summary": ai_summary
        }

    def _advanced_school_search(self, province: str = None, district: str = None, 
                               min_students: int = None, max_students: int = None,
                               min_teachers: int = None, max_teachers: int = None,
                               agency: str = None, limit: int = 10) -> Dict[str, Any]:
        """
        Advanced search with numeric ranges and multiple criteria.
        Proxies to SchoolSearchEngine.search_by_criteria
        """
        filters = {
            'province': self._normalize_province(province) if province else None,
            'district': district,
            'agency': self._normalize_agency(agency) if agency else None,
            'min_students': min_students,
            'max_students': max_students,
            'min_teachers': min_teachers,
            'max_teachers': max_teachers
        }
        
        # Remove None values
        filters = {k: v for k, v in filters.items() if v is not None}
        
        logger.info(f"🔬 Advanced Search Params: {filters}")
        
        results, total_count, _ = self.search_engine.search_by_criteria(filters, limit=limit)
        
        # Format results
        formatted = []
        for point in results:
            meta = point.payload.get('metadata', {})
            formatted.append({
                "school_name": meta.get("school_name"),
                "province": meta.get("province"),
                "district": meta.get("district"),
                "total_students": meta.get("total_students"),
                "total_teachers": meta.get("total_teachers"),
                "agency": meta.get("agency")
            })
            
        # AI Summary to prevent hallucination
        ai_summary = f"พบตามเงื่อนไขทั้งหมด {total_count} แห่ง แต่แสดงผลเพียง {len(formatted)} แห่ง"
        if total_count == len(formatted):
             ai_summary = f"พบตามเงื่อนไขทั้งหมด {total_count} แห่ง (แสดงครบแล้ว)"

        return {
            "tool": "advanced_school_search",
            "query": filters,
            "total_found": total_count,
            "count": len(formatted),
            "results": formatted,
            "ai_summary": ai_summary
        }

    def _normalize_school_name(self, name: str) -> Tuple[str, str]:
        """Remove common prefixes and extract grade if embedded in name"""
        if not name:
            return name, None
            
        import re
        
        # Convert Thai numerals
        name = self._thai_to_arabic_numerals(name)
        
        # Remove common prefixes (order matters - longer patterns first)
        prefixes_to_remove = [
            "โรงเรียน", "รร.", "ร.ร.", "รร", "วิทยาลัย", "โรง", "ศูนย์การศึกษา"
        ]
        for prefix in prefixes_to_remove:
            if name.startswith(prefix):
                name = name[len(prefix):]
                break  # Only remove one prefix
        
        name = name.strip()
        
        extracted_grade = None
        
        # Pattern matching for embedded grades
        grade_patterns = [
            # ปวช./ปวส. patterns
            (r'(ระดับ)?ประกาศนียบัตรวิชาชีพ(ชั้นสูง)?ปีที่\s*(\d+)', lambda m: f"ปวส.{m.group(3)}" if m.group(2) else f"ปวช.{m.group(3)}"),
            (r'(ระดับ)?ปวช\.?\s*(\d+)', lambda m: f"ปวช.{m.group(2)}"),
            (r'(ระดับ)?ปวส\.?\s*(\d+)', lambda m: f"ปวส.{m.group(2)}"),
            # มัธยม patterns
            (r'(ระดับ)?ชั้น?มัธยมศึกษาปีที่\s*(\d+)', lambda m: f"ม.{m.group(2)}"),
            (r'(ระดับ)?ชั้น?ม\.?\s*(\d+)', lambda m: f"ม.{m.group(2)}"),
            # ประถม patterns
            (r'(ระดับ)?ชั้น?ประถมศึกษาปีที่\s*(\d+)', lambda m: f"ป.{m.group(2)}"),
            (r'(ระดับ)?ชั้น?ป\.?\s*(\d+)', lambda m: f"ป.{m.group(2)}"),
            # อนุบาล patterns
            (r'(ระดับ)?ชั้น?อนุบาล\s*(\d+)?', lambda m: f"อนุบาล{m.group(2) or ''}"),
        ]
        
        for pattern, extractor in grade_patterns:
            match = re.search(pattern, name)
            if match:
                extracted_grade = extractor(match)
                name = re.sub(pattern + r'.*$', '', name)
                break
        
        # Generic cleanup for remaining "ระดับชั้น..." text
        name = re.sub(r'(ระดับ)?ชั้น.*$', '', name)
        
        return name.strip(), extracted_grade

    def _count_teachers(self, school_name: str = None, province: str = None,
                        district: str = None, gender: str = None, person_type: str = None, 
                        year: str = None, region: str = None) -> Dict[str, Any]:
        """Count teachers with various filters including person_type (ประเภทบุคลากร), year, and region"""
        logger.info(f"🔎 [CountTeachers] Called with: school={school_name}, province={province}, region={region}")
        
        # FIX: Detect if 'province' parameter is actually a region name
        from .constants import REGIONS
        
        # If province provided, check if it's actually a region
        if province:
            if province.startswith("ภาค") or province in REGIONS:
                 logger.info(f"🗺️ [CountTeachers] Province '{province}' is actually a region -> Cleaning up")
                 if not region:
                     region = province
                     logger.info(f"Promoted province to region: {region}")
                 
                 # CRITICAL: Always clear province if it's a region name to avoid "province='ภาคใต้'" query
                 province = None
        
        conditions = []
        
        resolved_school_id = None
        
        if school_name:
             # Disambiguation / Resolution
             ambiguity_check = self._resolve_school_ambiguity(school_name, province)
             if ambiguity_check['type'] == 'single':
                 resolved_school_id = ambiguity_check['data'].payload.get('metadata', {}).get('school_id')
                 logger.info(f"🎯 [CountTeachers] Resolved specific school ID: {resolved_school_id}")

             elif ambiguity_check['type'] == 'ambiguous':
                 exact_in_choices = [c for c in ambiguity_check['choices'] if c.get('school_name') == school_name]
                 if len(exact_in_choices) == 1:
                     target = exact_in_choices[0]
                     logger.info(f"🎯 [CountTeachers] Exact match found in ambiguous list. Overriding.")
                     resolved_school_id = target.get('school_id')
                 else:
                     logger.info(f"🤔 [CountTeachers] Ambiguous school name '{school_name}' -> Found {len(ambiguity_check['choices'])} matches")
                     return {
                         "tool": "count_teachers",
                         "ambiguous": True,
                         "total_found": len(ambiguity_check['choices']),
                         "choices": ambiguity_check['choices'],
                         "query": {"school_name": school_name}
                     }

        conditions = []
        
        if resolved_school_id:
            # PREFERRED: Filter by ID
            conditions.append(
                FieldCondition(key="metadata.school_id", match=MatchValue(value=str(resolved_school_id)))
            )
        elif school_name:
            # FALLBACK
            school_name, _ = self._normalize_school_name(school_name)
            conditions.append(
                FieldCondition(key="metadata.school_name", match=MatchText(text=school_name))
            )
        if province:
            province = self._normalize_province(province)
            conditions.append(
                FieldCondition(key="metadata.province", match=MatchValue(value=province))
            )
        if district:
            conditions.append(
                FieldCondition(key="metadata.district", match=MatchText(text=district))
            )
        if gender:
            conditions.append(
                FieldCondition(key="metadata.gender", match=MatchValue(value=gender))
            )
        if person_type:
            person_type = self._normalize_person_type(person_type)
            conditions.append(
                FieldCondition(key="metadata.person_type", match=MatchValue(value=person_type))
            )
        if year and not self._active_year:
            # Only add metadata.year filter when NOT using year-based collection routing
            conditions.append(
                FieldCondition(key="metadata.year", match=MatchValue(value=int(year)))
            )
        
        # Region filter - expand to multiple provinces
        if region:
            region_provinces = REGIONS.get(region, [])
            if region_provinces:
                logger.info(f"🗺️ [CountTeachers] Expanding region '{region}' to {len(region_provinces)} provinces")
                # Use "should" (OR) for multiple provinces
                province_conditions = [
                    FieldCondition(key="metadata.province", match=MatchValue(value=prov))
                    for prov in region_provinces
                ]
                conditions.append(
                    Filter(should=province_conditions)
                )
            
        scroll_filter = self._build_filter(conditions)
        
        # OPTIMIZATION: Use schools collection only when scope is narrow (no region)
        # Region-level totals are more accurate from teachers collection
        if not gender and not person_type and not school_name and not region:
            logger.info("⚡ Using Fast Ranking (Optimization) for Total Teachers")
            all_schools = self._scroll_all(self._get_collection("schools"), scroll_filter, limit=50000)
            
            ranked = []
            total_all = 0
            for r in all_schools:
                meta = r.payload.get("metadata", {})
                count = meta.get("total_teachers", 0)
                if count > 0:
                    ranked.append((meta.get("school_name", "Unknown"), count))
                    total_all += count
            
            ranked.sort(key=lambda x: x[1], reverse=True)
            
            # Fix structure
            top_10 = {}
            for name, count in ranked[:10]:
                top_10[name] = {"total": count}
                
            return {
                "tool": "count_teachers",
                "query": {"school_name": school_name, "province": province},
                "total_teachers": total_all,
                "total_found": len(ranked),  # Number of schools with teacher data
                "by_gender": {},
                "by_person_type": {},
                "by_school": top_10,
                "school_count": len(ranked)
            }
        
        scroll_filter = self._build_filter(conditions)
        # Increase limit for province-wide queries
        # OPTIMIZATION: Only fetch needed aggregation fields
        results = self._scroll_all(self._get_collection("teachers"), scroll_filter, limit=50000,
                                  with_payload=["metadata.school_name", "metadata.count", "metadata.gender", "metadata.person_type", "metadata.province"])
        
        # Aggregate by school and person_type
        schools = {}
        by_person_type = {}  # NEW: breakdown by position type
        total_count = 0
        total_male = 0
        total_female = 0
        
        for r in results:
            meta = r.payload.get("metadata", {})
            school = meta.get("school_name", "ไม่ระบุ")
            count = meta.get("count", 1)
            g = meta.get("gender", "-")
            pt = meta.get("person_type", "ไม่ระบุ")
            
            if school not in schools:
                schools[school] = {"total": 0, "male": 0, "female": 0, "province": meta.get("province")}
            
            schools[school]["total"] += count
            total_count += count
            
            # Count by person_type
            if pt not in by_person_type:
                by_person_type[pt] = 0
            by_person_type[pt] += count
            
            if g == "ชาย":
                schools[school]["male"] += count
                total_male += count
            elif g == "หญิง":
                schools[school]["female"] += count
                total_female += count
        
        # Sort by_person_type by count descending
        by_person_type = dict(sorted(by_person_type.items(), key=lambda x: x[1], reverse=True))
        
        # Flag if multiple schools were found
        is_multi_school = len(schools) > 1

        # FALLBACK: If total_count is 0 but we queried a specific school
        # Check SCHOOLS metadata for total_teachers
        if total_count == 0 and not person_type and not gender:
            logger.info("⚠️ No teachers found in deep stats, checking school metadata...")
            try:
                fallback_conditions = []
                if school_name:
                    sn_clean, _ = self._normalize_school_name(school_name)
                    fallback_conditions.append(FieldCondition(key="metadata.school_name", match=MatchText(text=sn_clean)))
                if province:
                    province = self._normalize_province(province)
                    fallback_conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))
                
                if fallback_conditions:
                    fb_filter = self._build_filter(fallback_conditions)
                    fb_results = self._scroll_all(self._get_collection("schools"), fb_filter, limit=50) 
                    
                    for r in fb_results:
                        meta = r.payload.get("metadata", {})
                        s_name = meta.get("school_name", "ไม่ระบุ")
                        s_prov = meta.get("province", "")
                        
                        t_teachers = meta.get("total_teachers", 0)
                        
                        if t_teachers > 0:
                            if s_name not in schools:
                                schools[s_name] = {"total": 0, "male": 0, "female": 0, "province": s_prov}
                            
                            schools[s_name]["total"] = max(schools[s_name]["total"], t_teachers)
                            total_count += t_teachers
            except Exception as e:
                logger.error(f"❌ Fallback to schools metadata failed for teachers: {e}")

        # HYBRID ENRICHMENT: If we found teachers data BUT total is low, check schools metadata for potentially higher total
        # This ensures we report the higher of the two sources
        elif total_count > 0 and school_name and len(schools) == 1:
            try:
                details = self.search_engine.get_school_details(school_name)
                if details:
                    metadata_total = details.get("total_teachers", 0)
                    if metadata_total > total_count:
                        logger.info(f"📊 HYBRID: Schools metadata has higher count ({metadata_total}) than teachers collection ({total_count})")
                        # Keep the breakdown from teachers collection, but note the discrepancy
                        # Update the total to the higher value from metadata
                        single_school_name = list(schools.keys())[0]
                        schools[single_school_name]["total"] = metadata_total
                        schools[single_school_name]["metadata_total"] = metadata_total
                        schools[single_school_name]["teachers_collection_total"] = total_count
                        total_count = metadata_total
                    elif total_count > metadata_total and metadata_total > 0:
                         logger.info(f"📊 HYBRID: Teachers collection has more data ({total_count}) than metadata ({metadata_total})")
                         # Teachers collection is richer, keep it
            except Exception as e:
                logger.debug(f"Hybrid enrichment failed: {e}")

        # Prepare AI Summary which drives the response
        ai_summary = f"พบข้อมูลครูทั้งหมด {total_count:,} คน"
        ai_hint = ""
        
        
        # New variable to hold fallback data
        fallback_students_data = None

        if total_count == 0:
            ai_summary = "ไม่พบข้อมูลครูตามเงื่อนไขที่ระบุครับ"
            
            # SMART FALLBACK: Robust Data Injection
            # If teacher data is missing for a specific school, automatically fetch student data
            # This ensures the LLM has something to talk about instead of dead-ending.
            if school_name or resolved_school_id:
                try:
                    # Determine target for fallback
                    target_name = school_name
                    if resolved_school_id:
                         # Fetch name from ID if possible, or just pass ID if count_students supports it (it relies on name mostly)
                         # Safe bet: Get details first to get precise name
                         details = self.search_engine.get_school_details(resolved_school_id)
                         if details:
                             target_name = details.get('school_name')
                    
                    if target_name:
                        logger.info(f"🔄 Fallback: Fetching student data for '{target_name}' to enrich empty teacher response")
                        # Call internal tool
                        fallback_data = self._count_students(school_name=target_name)
                        
                        if fallback_data.get('total_students', 0) > 0:
                            fallback_students_data = fallback_data
                            # result["data_missing"] = True  <-- Can't set result yet, define boolean
                            
                            
                            # Compatible Hint for older prompts
                            s_count = fallback_data['total_students']
                            # UPDATE: Use a more direct summary to prevent LLM from ignoring it
                            ai_summary = (f"ข้อมูลบุคลากรครูยังไม่ครบถ้วนในฐานข้อมูล แต่ระบบพบข้อมูล **นักเรียนทั้งหมด {s_count:,} คน** แทนครับ "
                                       f"(ระบบแนบข้อมูลนักเรียนให้แล้ว)")
                            
                            logger.info(f"✅ Fallback successful: Attached student data ({s_count})")
                except Exception as e:
                    logger.error(f"⚠️ Smart Fallback failed: {e}")
            
        elif schools:
            # Breakdown logic
             if len(schools) <= 5:
                details = []
                for s, info in schools.items():
                    details.append(f"- {s}: {info['total']:,} คน")
                ai_summary += "\n" + "\n".join(details)
             else:
                ai_summary += f" (กระจายอยู่ใน {len(schools)} โรงเรียน)"

        # FIX: If person_type filter is set but Qdrant didn't filter properly,
        # correct total_count using the application-level by_person_type breakdown
        if person_type and by_person_type:
            filtered_total = by_person_type.get(person_type, 0)
            if filtered_total > 0 and filtered_total != total_count:
                logger.info(f"🔧 [CountTeachers] Correcting total from {total_count} → {filtered_total} (person_type={person_type})")
                total_count = filtered_total
                # Also recalculate gender from filtered records only
                total_male = 0
                total_female = 0
                for r in results:
                    meta = r.payload.get("metadata", {})
                    pt = meta.get("person_type", "ไม่ระบุ")
                    if pt == person_type:
                        count = meta.get("count", 1)
                        g = meta.get("gender", "-")
                        if g == "ชาย":
                            total_male += count
                        elif g == "หญิง":
                            total_female += count

        logger.info(f"📊 [CountTeachers] total_count={total_count}, male={total_male}, female={total_female}, person_type={person_type}, by_person_type={by_person_type}")

        # Also update ai_summary after person_type correction
        if person_type:
            ai_summary = f"พบข้อมูล{person_type}ทั้งหมด {total_count:,} คน"

        result = {
            "tool": "count_teachers",
            "query": {"school_name": school_name, "province": province, "gender": gender, "person_type": person_type, "region": region},
            "total_teachers": total_count,
            "total_found": len(schools),  # Number of schools with data
            "by_gender": {"male": total_male, "female": total_female},
            "ai_summary": ai_summary,
            "by_person_type": by_person_type, 
            "by_school": dict(sorted(schools.items(), key=lambda x: x[1]['total'], reverse=True)[:10]), # Keep top 10 for by_school
            "school_count": len(schools),
            "is_multi_school": is_multi_school, # Keep this flag
            "fallback_students": fallback_students_data,
            "data_missing": (fallback_students_data is not None)
        }

        # FUZZY SUGGESTION FALLBACK
        if total_count == 0 and school_name:
             suggestions = self._suggest_schools(school_name)
             if suggestions:
                 result["found"] = False
                 result["suggestions"] = suggestions
        
        return result
    
    def _count_students(self, school_name: str = None, province: str = None,
                        district: str = None, grade: str = None, 
                        gender: str = None, year: str = None, 
                        agency: str = None, **kwargs) -> Dict[str, Any]:
        """Count students with various filters including year"""
        
        # 0. DISAMBIGUATION CHECK
        # Only if searching by specific school name, and NOT by year/grade/gender deeply yet (to fail fast)
        resolved_school_id = None

        if school_name:
             # If user supplied province, it reduces ambiguity, pass it.
             ambiguity_check = self._resolve_school_ambiguity(school_name, province)
             if ambiguity_check['type'] == 'single':
                 resolved_school_id = ambiguity_check['data'].payload.get('metadata', {}).get('school_id')
                 logger.info(f"🎯 Resolved specific school ID: {resolved_school_id}")

             elif ambiguity_check['type'] == 'ambiguous':
                 # SMART RESOLUTION: Check if one choice exactly matches the query
                 exact_in_choices = [c for c in ambiguity_check['choices'] if c.get('school_name') == school_name]
                 if len(exact_in_choices) == 1:
                     # Found exact match! Override ambiguity and use this one.
                     target = exact_in_choices[0]
                     logger.info(f"🎯 Exact match '{school_name}' found in ambiguous list. Overriding.")
                     resolved_school_id = target.get('school_id')
                 else:
                     logger.info(f"🤔 Ambiguous school name '{school_name}' -> Found {len(ambiguity_check['choices'])} matches")
                     return {
                         "tool": "count_students",
                         "ambiguous": True,
                         "total_students": 0,  # Add for consistent access
                         "total_found": len(ambiguity_check['choices']),
                         "choices": ambiguity_check['choices'],
                         "query": {"school_name": school_name}
                     }
        
        conditions = []
        
        if resolved_school_id:
            # PREFERRED: Filter by ID if we successfully resolved it
            conditions.append(
                FieldCondition(key="metadata.school_id", match=MatchValue(value=str(resolved_school_id)))
            )
        elif school_name:
            # FALLBACK: Filter by name if ID resolution failed for some reason
            school_name, extracted_grade = self._normalize_school_name(school_name)
            conditions.append(
                FieldCondition(key="metadata.school_name", match=MatchText(text=school_name))
            )
            # Use extracted grade if main grade is missing
            if not grade and extracted_grade:
                grade = extracted_grade
        
        if province and not resolved_school_id:
            # Only add province filter if we haven't already locked onto a specific ID
            # (ID implies province, so redundant, but safer to keep if ID missing)
            province = self._normalize_province(province)
            conditions.append(
                FieldCondition(key="metadata.province", match=MatchValue(value=province))
            )

        # Handle Region from kwargs (CRITICAL FIX for Ranking by Region)
        region = kwargs.get('region')
        if region and not province and not resolved_school_id:
            region_provinces = REGIONS.get(region, [])
            if region_provinces:
                logger.info(f"Adding Region Filter: {region} ({len(region_provinces)} provinces)")
                conditions.append(
                    Filter(should=[
                        FieldCondition(key="metadata.province", match=MatchValue(value=p))
                        for p in region_provinces
                    ])
                )

        if district:
            conditions.append(
                FieldCondition(key="metadata.district", match=MatchText(text=district))
            )
        if grade:
            grade = self._normalize_grade(grade)
            if grade == "อนุบาล":
                # Handle Generic Kindergarten (Any level)
                conditions.append(
                    Filter(
                        should=[
                            # Catch "อนุบาล 1", "อนุบาล 2", "ชั้นอนุบาล" using Text Match
                            FieldCondition(key="metadata.grade", match=MatchText(text="อนุบาล")),
                            FieldCondition(key="metadata.grade", match=MatchText(text="ปฐมวัย")),
                            # Catch abbreviations (Exact Value)
                            FieldCondition(key="metadata.grade", match=MatchValue(value="อ.1")),
                            FieldCondition(key="metadata.grade", match=MatchValue(value="อ.2")),
                            FieldCondition(key="metadata.grade", match=MatchValue(value="อ.3")),
                        ]
                    )
                )
            elif grade:
                conditions.append(
                    FieldCondition(key="metadata.grade", match=MatchText(text=grade))
                )
        if gender:
            conditions.append(
                FieldCondition(key="metadata.gender", match=MatchValue(value=gender))
            )
        if year and not self._active_year:
            # Only add metadata.year filter when NOT using year-based collection routing
            # (year-based routing already selects the correct collection)
            conditions.append(
                FieldCondition(key="metadata.year", match=MatchValue(value=int(year)))
            )

            
        # OPTIMIZATION: If ranking by total students (no deep filters), use schools collection
        # This avoids aggregating 700k records and bypasses the 10k limit
        
        scroll_filter = self._build_filter(conditions)
        
        if not grade and not gender and not school_name and (not year or self._active_year):
            try:
                logger.info("⚡ Using Fast Ranking (Optimization) for Total Students")
                # Fetch all schools from SCHOOLS collection (has pre-aggregated totals)
                all_schools = self._scroll_all(self._get_collection("schools"), scroll_filter, limit=50000)
                
                # Sort by total_students
                ranked = []
                total_all = 0
                for r in all_schools:
                    meta = r.payload.get("metadata", {})
                    count = meta.get("total_students", 0)
                    if count > 0:
                        ranked.append((meta.get("school_name", "Unknown"), count))
                        total_all += count
                
                # Sort descending
                ranked.sort(key=lambda x: x[1], reverse=True)
                
                # Fix structure to match expected format (dict of dicts)
                top_10 = {}
                for name, count in ranked[:10]:
                    top_10[name] = {"total": count}
                    
                # ENHANCEMENT: Also fetch grade/gender breakdown from students collection
                # This provides richer data for province-level queries
                by_gender = {"male": 0, "female": 0}
                by_grade = {}
                
                try:
                    # Fetch a sample of students data to get grade/gender breakdown
                    # We use a reasonable limit since we just need aggregation
                    # OPTIMIZATION: Only fetch needed aggregation fields
                    student_results = self._scroll_all(self._get_collection("students"), scroll_filter, limit=50000,
                                                      with_payload=["metadata.count", "metadata.gender", "metadata.grade"])
                    
                    for r in student_results:
                        meta = r.payload.get("metadata", {})
                        count = meta.get("count", 1)
                        g = meta.get("gender", "-")
                        grade_val = meta.get("grade", "ไม่ระบุ")
                        
                        # Aggregate by gender
                        if g == "ชาย":
                            by_gender["male"] += count
                        elif g == "หญิง":
                            by_gender["female"] += count
                        
                        # Aggregate by grade
                        if grade_val not in by_grade:
                            by_grade[grade_val] = {"total": 0, "male": 0, "female": 0}
                        by_grade[grade_val]["total"] += count
                        if g == "ชาย":
                            by_grade[grade_val]["male"] += count
                        elif g == "หญิง":
                            by_grade[grade_val]["female"] += count
                    
                    logger.info(f"📊 Province breakdown: {len(by_grade)} grades, {by_gender['male']} male, {by_gender['female']} female")
                except Exception as e:
                    logger.warning(f"⚠️ Could not fetch grade/gender breakdown: {e}")
                    
                return {
                    "tool": "count_students",
                    "query": {"school_name": school_name, "province": province},
                    "total_students": total_all,
                    "by_gender": by_gender,
                    "by_school": top_10,
                    "school_count": len(ranked),
                    "student_breakdown": by_grade,  # Add grade breakdown
                    "student_breakdown_source": "edu_students_v5" if by_grade else None,
                    "ambiguous_schools": []
                }
            except Exception as e:
                logger.error(f"❌ OPTIMIZATION CRASHED: {e}")
                import traceback
                logger.error(traceback.format_exc())
        # Increase limit for province-wide queries with grade/gender filters
        # OPTIMIZATION: Only fetch needed aggregation fields
        results = self._scroll_all(self._get_collection("students"), scroll_filter, limit=50000,
                                  with_payload=["metadata.school_name", "metadata.count", "metadata.gender", "metadata.province"])
        
        # Aggregate
        schools = {}
        total_count = 0
        total_male = 0
        total_female = 0
        
        # Track if this might be a multi-school query (e.g. "สวนกุหลาบ" matches many schools)
        target_name = school_name.replace(" ", "") if school_name else None
        
        for r in results:
            meta = r.payload.get("metadata", {})
            school = meta.get("school_name", "ไม่ระบุ")
            
            # INCLUDE all matching schools (don't filter out branches)
            # This allows "สวนกุหลาบ" to return all สวนกุหลาบวิทยาลัย branches
            
            count = meta.get("count", 1)
            g = meta.get("gender", "-")
            
            if school not in schools:
                schools[school] = {"total": 0, "male": 0, "female": 0, "province": meta.get("province")}
            
            schools[school]["total"] += count
            total_count += count
            
            if g == "ชาย":
                schools[school]["male"] += count
                total_male += count
            elif g == "หญิง":
                schools[school]["female"] += count
                total_female += count
        
        is_multi_school = len(schools) > 1
        
        # SMART REDUCTION: If multiple schools found, but one matches exactly, pick that one.
        if is_multi_school and school_name:
            # 1. Try strict equality
            exact_matches = [s for s in schools.keys() if s == school_name]
            
            # 2. If no strict match, try normalized (remove whitespace, casing)
            if not exact_matches:
                target_clean, _ = self._normalize_school_name(school_name)
                # Check normalized key vs normalized target
                exact_matches = [s for s in schools.keys() if self._normalize_school_name(s)[0] == target_clean]
            
            if len(exact_matches) == 1:
                # Found exactly one school that matches the user's query perfectly
                target = exact_matches[0]
                logger.info(f"🎯 Exact match found in ambiguous list: '{target}'. Ignoring others.")
                # Filter down to just this one
                schools = {target: schools[target]}
                total_count = schools[target]['total']
                total_male = schools[target]['male']
                total_female = schools[target]['female']
                is_multi_school = False
        
        # SUPER FALLBACK: If still ambiguous but user gave a school_name, try fetching it directly
        # logic: sometimes 'search' returns noise, but 'get_details' works perfectly.
        if is_multi_school and school_name:
             try:
                 details = self.search_engine.get_school_details(school_name)
                 if details:
                     logger.info(f"🎯 Direct fetch found exact match for '{school_name}', overriding ambiguous list.")
                     # Construct single school result manually
                     s_name = details['school_name']
                     t_students = details.get('total_students', 0)
                     schools = {s_name: {"total": t_students, "male": 0, "female": 0, "province": details.get('province', '')}} # Gender unknown from metadata
                     total_count = t_students
                     is_multi_school = False
                     
                     # Note: The breakdown fetch logic below will now verify and attach breakdown
                     # Manual injection of school_id to results metadata so the breakdown fetcher below can find it
                     logger.info(f"💉 Injecting fallback school_id {details.get('school_id')} for breakdown fetch")
                     # We fake a result object or just rely on the fact that 'schools' is now size 1.
                     # But the breakdown fetcher (lines 1180+) looks for 'school_id' in 'results'.
                     # Let's just manually fetch it here for safety.
                     if details.get('school_id'):
                         stats = self.search_engine.get_student_statistics(details.get('school_id'))
                         if stats:
                             # Attach directly to a temporary holder that we can merge later or just modify result structure
                             # Actually, easiest is to just let the standard logic run, but we need to ensure school_id discovery works.
                             # Standard logic iterates 'results'. We don't have 'results' update here.
                             # So let's just do it manually here.
                             result["student_breakdown"] = stats.get("by_grade", {})
                             result["student_breakdown_source"] = stats.get("source")
                             logger.info("📊 Attached student breakdown (Fallback path)")
             except Exception as e:
                 logger.error(f"Fallback fetch failed: {e}")


        
        # FALLBACK: If total_count is 0 but we queried a specific school/province
        # Check the SCHOOLS collection metadata, which often has the total count even if the STUDENTS collection is empty.
        if total_count == 0 and not grade and not gender and not year:
            logger.info("⚠️ No students found in deep stats, checking school metadata...")
            try:
                # Reuse the logic for building filter but point to SCHOOLS collection
                # Note: 'school_name' in schools collection matches 'school_name' key
                fallback_conditions = []
                if school_name:
                    # Clean the name for schools collection match
                    sn_clean, _ = self._normalize_school_name(school_name)
                    fallback_conditions.append(FieldCondition(key="metadata.school_name", match=MatchText(text=sn_clean)))
                if province:
                    province = self._normalize_province(province)
                    fallback_conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))
                if district:
                    fallback_conditions.append(FieldCondition(key="metadata.district", match=MatchText(text=district)))

                if fallback_conditions:
                    fb_filter = self._build_filter(fallback_conditions)
                    # Fetch from SCHOOLS collection
                    fb_results = self._scroll_all(self._get_collection("schools"), fb_filter, limit=50) # Limit low for metadata check
                    
                    for r in fb_results:
                        meta = r.payload.get("metadata", {})
                        s_name = meta.get("school_name", "ไม่ระบุ")
                        s_prov = meta.get("province", "")
                        
                        # Get total_students from metadata
                        t_students = meta.get("total_students", 0)
                        
                        if t_students > 0:
                            if s_name not in schools:
                                schools[s_name] = {"total": 0, "male": 0, "female": 0, "province": s_prov}
                            
                            # Add to totals
                            schools[s_name]["total"] = max(schools[s_name]["total"], t_students) # Use max to avoid double counting if mixed
                            total_count += t_students
                            
                            # Note: We can't infer male/female split from metadata only
            except Exception as e:
                logger.error(f"❌ Fallback to schools metadata failed: {e}")

        result = {
            "tool": "count_students",
            "query": {"school_name": school_name, "province": province, "grade": grade, "gender": gender},
            "total_students": total_count,
            "by_gender": {"male": total_male, "female": total_female},
            "by_school": dict(sorted(schools.items(), key=lambda x: x[1]['total'], reverse=True)[:20]),
            "school_count": len(schools),
            "is_multi_school": is_multi_school
        }

        # ENHANCEMENT: If single school found, attach detailed breakdown
        # This fixes "How many M.1 students" queries failing because get_school_details wasn't called
        if len(schools) == 1:
            try:
                single_school_name = list(schools.keys())[0]
                # Try to find school_id from results or schools metadata logic above
                school_id = None
                
                # Check results first
                for r in results:
                    meta = r.payload.get("metadata", {})
                    if meta.get("school_name") == single_school_name:
                         school_id = meta.get("school_id")
                         break
                
                # If not found (e.g. fallback logic), try to search for it quickly or skip
                if not school_id and school_name:
                     # Quick lookup for ID
                     details = self.search_engine.get_school_details(single_school_name)
                     if details:
                         school_id = details.get("school_id")
                
                if school_id:
                    stats = self.search_engine.get_student_statistics(school_id)
                    if stats:
                        result["student_breakdown"] = stats.get("by_grade", {})
                        result["student_breakdown_source"] = stats.get("source")
                        logger.info(f"📊 Attached student breakdown to count_students for {single_school_name}")
            except Exception as e:
                logger.error(f"❌ Failed to attach student breakdown in count_students: {e}")


        # FUZZY SUGGESTION FALLBACK
        if total_count == 0 and school_name:
             suggestions = self._suggest_schools(school_name)
             if suggestions:
                 result["found"] = False
                 result["suggestions"] = suggestions
        
        return result
    
    def _count_schools(self, province: str = None, district: str = None,
                       subdistrict: str = None, agency: str = None, region: str = None, **kwargs) -> Dict[str, Any]:
        """Count schools in an area including subdistrict (ตำบล/แขวง) and region"""
        
        # Strip inputs
        if province: province = province.strip()
        if region: region = region.strip()

        # FIX: Detect if 'province' parameter is actually a region name
        from .constants import REGIONS
        if province and not region:
            if province.startswith("ภาค") or province in REGIONS:
                logger.info(f"🗺️ [CountSchools] Detected region in province param: '{province}' -> Moving to region")
                region = province
                province = None
        
        conditions = []
        
        # Region filter - expand to multiple provinces
        if region:
            region_provinces = REGIONS.get(region, [])
            if region_provinces:
                logger.info(f"🗺️ [CountSchools] Expanding region '{region}' to {len(region_provinces)} provinces")
                province_conditions = [
                    FieldCondition(key="metadata.province", match=MatchValue(value=prov))
                    for prov in region_provinces
                ]
                conditions.append(
                    Filter(should=province_conditions)
                )
        elif province:
            province = self._normalize_province(province)
            conditions.append(
                FieldCondition(key="metadata.province", match=MatchValue(value=province))
            )
        if district:
            conditions.append(
                FieldCondition(key="metadata.district", match=MatchText(text=district))
            )
        if subdistrict:
            conditions.append(
                FieldCondition(key="metadata.subdistrict", match=MatchText(text=subdistrict))
            )
        if agency:
            # Normalize agency abbreviations (e.g. สพฐ → สำนักงานคณะกรรมการการศึกษาขั้นพื้นฐาน)
            agency = self._normalize_agency(agency)
            conditions.append(
                FieldCondition(key="metadata.agency", match=MatchValue(value=agency))
            )
        
        scroll_filter = self._build_filter(conditions)
        # Increase limit for province-wide school queries
        # OPTIMIZATION: Only fetch fields needed for grouping/counting
        results = self._scroll_all(self._get_collection("schools"), scroll_filter, limit=20000,
                                  with_payload=["metadata.school_id", "metadata.school_name", "metadata.province", "metadata.agency", "metadata.district", "metadata.total_students", "metadata.total_teachers"])
        
        # Group by agency (and deduplicate)
        agencies = {}
        unique_keys = set()
        
        # Aggregation Stats
        total_students_all = 0
        total_teachers_all = 0
        
        for r in results:
            meta = r.payload.get("metadata", {})
            sid = meta.get("school_id")
            name = meta.get("school_name", "ไม่ระบุ")
            
            # Use same fallback key logic
            key = sid if sid else f"{name}_{meta.get('province','')}"
            
            if key in unique_keys:
                continue
            unique_keys.add(key)
            
            ag = meta.get("agency", "ไม่ระบุ")
            agencies[ag] = agencies.get(ag, 0) + 1
            
            # Also track by district for breakdown
            dist = meta.get("district", "ไม่ระบุ")
            if "districts" not in locals():
                districts = {}
            districts[dist] = districts.get(dist, 0) + 1
            
            # Aggregate Students & Teachers
            # Note: schools collection metadata has pre-calculated totals
            total_students_all += meta.get("total_students", 0)
            total_teachers_all += meta.get("total_teachers", 0)
        
        # Sort districts by count and take top 10
        sorted_districts = sorted(districts.items() if "districts" in locals() else [], 
                                  key=lambda x: x[1], reverse=True)[:10]
        
        return {
            "tool": "count_schools",
            "query": {"province": province, "district": district, "agency": agency, "region": region},
            "total_schools": len(unique_keys),
            "total_students": total_students_all,
            "total_teachers": total_teachers_all,
            "by_agency": agencies,
            "by_district": dict(sorted_districts) if sorted_districts else None
        }
    
    def _get_ratio(self, school_name: str = None, province: str = None, **kwargs) -> Dict[str, Any]:
        """Get student-teacher ratio"""
        conditions = []
        cleaned_school_name = school_name
        
        if school_name:
            cleaned_school_name, _ = self._normalize_school_name(school_name)
            conditions.append(
                FieldCondition(key="metadata.school_name", match=MatchText(text=cleaned_school_name))
            )
        if province:
            province = self._normalize_province(province)
            conditions.append(
                FieldCondition(key="metadata.province", match=MatchValue(value=province))
            )
        
        scroll_filter = self._build_filter(conditions)
        results = self._scroll_all(self._get_collection("ratios"), scroll_filter, limit=50)
        
        ratios = []
        for r in results:
            meta = r.payload.get("metadata", {})
            ratios.append({
                "school_name": meta.get("school_name"),
                "ratio": meta.get("ratio", 0),
                "students": meta.get("total_students", 0),
                "teachers": meta.get("total_teachers", 0),
                "province": meta.get("province"),
            })

        # Fallback: compute ratio from students + teachers if ratios collection is missing
        if not ratios and school_name:
            try:
                student_result = self._count_students(school_name=school_name, province=province)
                teacher_result = self._count_teachers(school_name=school_name, province=province)

                # If ambiguous, let caller handle suggestions via existing path
                if student_result.get("ambiguous") or teacher_result.get("ambiguous"):
                    logger.info("⚠️ Ratio fallback: ambiguous school name, skipping computed ratio")
                else:
                    total_students = student_result.get("total_students", 0)
                    total_teachers = teacher_result.get("total_teachers", 0)

                    if total_students > 0 and total_teachers > 0:
                        # Prefer canonical school name from results if available
                        school_label = cleaned_school_name or school_name
                        if student_result.get("by_school"):
                            school_label = next(iter(student_result["by_school"].keys()), school_label)
                        elif teacher_result.get("by_school"):
                            school_label = next(iter(teacher_result["by_school"].keys()), school_label)

                        ratios.append({
                            "school_name": school_label,
                            "ratio": round(total_students / total_teachers, 1),
                            "students": total_students,
                            "teachers": total_teachers,
                            "province": province,
                            "computed": True,
                            "source": "students_teachers"
                        })
                        logger.info("✅ Ratio fallback computed from students + teachers")
            except Exception as e:
                logger.warning(f"⚠️ Ratio fallback failed: {e}")
        
        return {
            "tool": "get_ratio",
            "query": {"school_name": school_name, "province": province},
            "ratios": sorted(ratios, key=lambda x: x['ratio'], reverse=True)[:10],
            "suggestions": self._suggest_schools(school_name) if not ratios and school_name else None,
            "found": False if not ratios and school_name else True
        }
    
    def _compare(self, entity1: str, entity2: str, metric: str = "students", **kwargs) -> Dict[str, Any]:
        """Compare two entities (schools, provinces, or regions)"""
        result1 = None
        result2 = None
        
        # Normalize Thai metric aliases
        metric_aliases = {
            "จำนวนโรงเรียน": "schools",
            "โรงเรียน": "schools",
            "school": "schools",
            "จำนวนนักเรียน": "students",
            "นักเรียน": "students",
            "student": "students",  
            "จำนวนครู": "teachers",
            "ครู": "teachers",
            "teacher": "teachers",
            "บุคลากร": "teachers",
            "อัตราส่วน": "ratio",
        }
        metric = metric_aliases.get(metric, metric) if metric else "students"
        logger.info(f"📊 [Compare] Normalized metric: {metric}")
        
        # Helper to get data for an entity (Region -> Province -> School)
        def get_data(entity):
            # 1. Try Region
            region = self._normalize_region(entity)
            if region:
                logger.info(f"📍 Detected region entity: {entity} -> {region}")
                return self._get_region_data(region, metric)
            
            # 2. Try Province (Prioritize over school to avoid ambiguous matches like 'กระบี่' -> 'รร.กระบี่')
            # Check if likely a province
            prov_norm = self._normalize_province(entity)
            if prov_norm != entity or prov_norm in ["กรุงเทพมหานคร"]:
                 # It normalized to something standard, or is a known province like BKK
                 pass
            
            # We don't have a simple "is_province" check freely available without heavy import or list logic,
            # but we can try to query validity or just try province query if it looks like one.
            # Simplified: Try searching as province first. If it returns substantial data, use it?
            # Or just use the metric logic carefully.
            
            # Better approach: Explicitly check our hardcoded regions/constants if possible, 
            # but for now let's flip the order in the metric block if it looks like a province.
            
            from .constants import REGIONS
            all_provinces = set()
            for p_list in REGIONS.values():
                all_provinces.update(p_list)
            
            is_province = prov_norm in all_provinces or prov_norm == "กรุงเทพมหานคร"

            if metric == "students":
                if is_province:
                     logger.info(f"📍 Detected province entity: {entity} -> {prov_norm}")
                     return self._count_students(province=prov_norm)
                
                # Check school first
                res_school = self._count_students(school_name=entity)
                
                # Handle ambiguous case - try to pick best match
                if res_school.get("ambiguous") and res_school.get("choices"):
                    choices = res_school["choices"]
                    # Find exact name match in choices
                    clean_entity = entity.replace("โรงเรียน", "").strip()
                    for choice in choices:
                        if choice.get("school_name") == entity or choice.get("school_name") == clean_entity:
                            logger.info(f"🎯 [Compare] Auto-resolved ambiguous '{entity}' to exact match")
                            # Re-query with school_id
                            return self._count_students(school_name=choice.get("school_name"), province=choice.get("province"))
                    # If no exact match, use first choice (best semantic match)
                    best = choices[0]
                    logger.info(f"🎯 [Compare] Auto-resolved ambiguous '{entity}' to best match: {best.get('school_name')}")
                    return self._count_students(school_name=best.get("school_name"), province=best.get("province"))
                
                if res_school.get("total_students", 0) > 0:
                    return res_school
                
                # Try province if school failed
                res_prov = self._count_students(province=entity)
                if res_prov.get("total_students", 0) > 0:
                    return res_prov
                
                # If both failed, prefer school result if it has suggestions
                return res_school if res_school.get("suggestions") else res_prov
                
            elif metric == "teachers":
                if is_province:
                     logger.info(f"📍 Detected province entity: {entity} -> {prov_norm}")
                     return self._count_teachers(province=prov_norm)

                res_school = self._count_teachers(school_name=entity)
                
                # Handle ambiguous case - try to pick best match
                if res_school.get("ambiguous") and res_school.get("choices"):
                    choices = res_school["choices"]
                    clean_entity = entity.replace("โรงเรียน", "").strip()
                    for choice in choices:
                        if choice.get("school_name") == entity or choice.get("school_name") == clean_entity:
                            logger.info(f"🎯 [Compare] Auto-resolved ambiguous '{entity}' to exact match")
                            return self._count_teachers(school_name=choice.get("school_name"), province=choice.get("province"))
                    best = choices[0]
                    logger.info(f"🎯 [Compare] Auto-resolved ambiguous '{entity}' to best match: {best.get('school_name')}")
                    return self._count_teachers(school_name=best.get("school_name"), province=best.get("province"))
                
                if res_school.get("total_teachers", 0) > 0:
                    return res_school

                res_prov = self._count_teachers(province=entity)
                if res_prov.get("total_teachers", 0) > 0:
                    return res_prov

                # If both failed, prefer school result if it has suggestions
                return res_school if res_school.get("suggestions") else res_prov
                
            elif metric == "schools":
                # Schools metric only applies to Province/Region (not school vs school usually)
                return self._count_schools(province=entity)
                
            elif metric == "ratio":
                if is_province:
                    # Specialized province ratio logic or reuse get_ratio with province param?
                    # _get_ratio supports province
                    return self._get_ratio(province=prov_norm)
                return self._get_ratio(school_name=entity)
                
            return None

        result1 = get_data(entity1)
        result2 = get_data(entity2)
        
        return {
            "tool": "compare",
            "entity1": {"name": entity1, "data": result1},
            "entity2": {"name": entity2, "data": result2},
            "metric": metric
        }
    
    def _ranking(self, metric: str = None, order: str = "most", scope: str = "school",
                 province: str = None, limit: int = 5, type: str = None, **kwargs) -> Dict[str, Any]:
        """Get ranking of schools or provinces by a metric"""
        # Handle parameter alias: 'type' -> 'metric' (LLM sometimes sends 'type' instead of 'metric')
        if not metric and type:
            metric = type
        if not metric:
            metric = "students"  # default
        
        # Auto-detect if 'province' is actually a region name
        region = kwargs.get('region')
        if province and not region:
            if province.startswith("ภาค") or province in REGIONS:
                logger.info(f"🗺️ [Ranking] Province '{province}' is actually a region -> promoting")
                region = province
                kwargs['region'] = region
                province = None
        
        # Auto-downgrade scope when region is set but province is missing
        if region and not province and scope in ["district", "districts"]:
            logger.info(f"🔄 [Ranking] Downgrading scope from '{scope}' to 'school' (region query without province)")
            scope = "school"
        
        # Normalize Thai metric aliases (comprehensive)
        metric_aliases = {
            "จำนวนครู": "teachers",
            "ครู": "teachers",
            "บุคลากร": "teachers",
            "teacher": "teachers",
            "จำนวนนักเรียน": "students",
            "นักเรียน": "students",
            "student": "students",
            "จำนวนโรงเรียน": "schools",
            "โรงเรียน": "schools",
            "school": "schools",
            "อัตราส่วน": "ratio",
            "อัตราส่วนครูต่อนักเรียน": "ratio",
            "ครูต่อนักเรียน": "ratio",
        }
        metric = metric_aliases.get(metric, metric)
        logger.info(f"📊 [Ranking] Normalized metric: {metric}")

        
        limit = int(limit)
        
        # Aggregate ranking by area (province/district/subdistrict) for students/teachers/ratio
        scope_norm = scope or "school"
        if metric in ["students", "teachers", "ratio"] and scope_norm in ["province", "provinces", "district", "districts", "subdistrict", "subdistricts"]:
            group_key_map = {
                "province": "province",
                "provinces": "province",
                "district": "district",
                "districts": "district",
                "subdistrict": "subdistrict",
                "subdistricts": "subdistrict",
            }
            group_key = group_key_map.get(scope_norm, "province")
            if group_key in ["district", "subdistrict"] and not province:
                return {"error": f"Ranking by {group_key} requires province"}

            conditions = []
            if kwargs.get("region"):
                provinces = REGIONS.get(kwargs.get("region"), [])
                if provinces:
                    conditions.append(
                        FieldCondition(key="metadata.province", match=MatchAny(any=provinces))
                    )
            if province:
                conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))
            if group_key == "subdistrict" and kwargs.get("district"):
                conditions.append(FieldCondition(key="metadata.district", match=MatchText(text=kwargs.get("district"))))

            scroll_filter = self._build_filter(conditions)
            results = self._scroll_all(
                self._get_collection("schools"),
                scroll_filter,
                limit=200000,
                with_payload=[
                    "metadata.province",
                    "metadata.district",
                    "metadata.subdistrict",
                    "metadata.total_students",
                    "metadata.total_teachers",
                ],
            )

            aggregates: Dict[str, Dict[str, float]] = {}
            for r in results:
                meta = r.payload.get("metadata", {})
                key = meta.get(group_key)
                if not key:
                    continue
                students = meta.get("total_students") or 0
                teachers = meta.get("total_teachers") or 0
                entry = aggregates.setdefault(key, {"students": 0, "teachers": 0})
                if isinstance(students, (int, float)):
                    entry["students"] += students
                if isinstance(teachers, (int, float)):
                    entry["teachers"] += teachers

            items = []
            for name, totals in aggregates.items():
                if metric == "students":
                    count = totals["students"]
                elif metric == "teachers":
                    count = totals["teachers"]
                else:
                    if not totals["students"]:
                        continue
                    count = totals["teachers"] / totals["students"]
                items.append((name, count))

        elif metric == "students":
            if kwargs.get('region'):
                # For region ranking: Get all provinces in region, count each, then flatten
                provinces = REGIONS.get(kwargs.get('region'), [])
                items = []
                # Limit provinces to avoid massive slowdown - or just aggregated list?
                # Actually, counting students by school for WHOLE region is expensive.
                # Optimization: For Region ranking, maybe we list top schools by province?
                # Or we call _count_students for region (which returns by_school now?)
                # Wait, _count_students(region=...) returns by_school top 10?
                data = self._count_students(region=kwargs.get('region'))
                items = [(k, v["total"]) for k, v in data.get("by_school", {}).items()]
            else:
                data = self._count_students(province=province)
                items = [(k, v["total"]) for k, v in data.get("by_school", {}).items()]
        elif metric == "teachers":
            if kwargs.get('region'):
                data = self._count_teachers(region=kwargs.get('region'))
                items = [(k, v["total"]) for k, v in data.get("by_school", {}).items()]
            else:
                data = self._count_teachers(province=province)
                items = [(k, v["total"]) for k, v in data.get("by_school", {}).items()]
        elif metric == "schools":
            # Ranking provinces by number of schools
            if scope in ["district", "districts"]:
                if not province:
                    return {"error": "Ranking by district requires province"}
                conditions = [FieldCondition(key="metadata.province", match=MatchValue(value=province))]
                # Optional district filter for sub-scope
                if kwargs.get("district"):
                    conditions.append(FieldCondition(key="metadata.district", match=MatchText(text=kwargs.get("district"))))
                scroll_filter = self._build_filter(conditions)
                results = self._scroll_all(
                    self._get_collection("schools"),
                    scroll_filter,
                    limit=200000,
                    with_payload=["metadata.district"]
                )
                counts = {}
                for r in results:
                    meta = r.payload.get("metadata", {})
                    dist = meta.get("district")
                    if not dist:
                        continue
                    counts[dist] = counts.get(dist, 0) + 1
                items = list(counts.items())
            elif scope in ["subdistrict", "subdistricts"]:
                if not province:
                    return {"error": "Ranking by subdistrict requires province"}
                conditions = [FieldCondition(key="metadata.province", match=MatchValue(value=province))]
                if kwargs.get("district"):
                    conditions.append(FieldCondition(key="metadata.district", match=MatchText(text=kwargs.get("district"))))
                scroll_filter = self._build_filter(conditions)
                results = self._scroll_all(
                    self._get_collection("schools"),
                    scroll_filter,
                    limit=200000,
                    with_payload=["metadata.subdistrict"]
                )
                counts = {}
                for r in results:
                    meta = r.payload.get("metadata", {})
                    sub = meta.get("subdistrict")
                    if not sub:
                        continue
                    counts[sub] = counts.get(sub, 0) + 1
                items = list(counts.items())
            elif scope in ["province", "provinces"] or (not province and scope == "school"):
                scope = "province"
                conditions = []
                if kwargs.get('region'):
                    provinces = REGIONS.get(kwargs.get('region'), [])
                    if provinces:
                        conditions.append(
                            FieldCondition(key="metadata.province", match=MatchAny(any=provinces))
                        )
                scroll_filter = self._build_filter(conditions)
                results = self._scroll_all(
                    self._get_collection("schools"),
                    scroll_filter,
                    limit=200000,
                    with_payload=["metadata.province"]
                )
                counts = {}
                for r in results:
                    meta = r.payload.get("metadata", {})
                    prov = meta.get("province")
                    if not prov:
                        continue
                    counts[prov] = counts.get(prov, 0) + 1
                items = list(counts.items())
            else:
                return {"error": "Ranking metric 'schools' requires province scope"}
        else:
            return {"error": f"Ranking metric '{metric}' not supported"}
        
        # Sort based on order
        reverse = order == "most"
        items.sort(key=lambda x: x[1], reverse=reverse)
        
        ranking = []
        for i, (name, count) in enumerate(items[:limit], 1):
            ranking.append({"rank": i, "name": name, "count": count})
        
        result = {
            "tool": "ranking",
            "metric": metric,
            "order": order,
            "scope": scope,
            "province": province,
            "ranking": ranking,
            "guidance": "REQUIRED: Start with an intro (e.g. 'Here are the top schools...') and END with an analysis of the #1 school."
        }
        logger.info(f"DEBUG RANKING RESULT: {result}")
        return result
    
    def _list_schools(self, province: str = None, district: str = None,
                      subdistrict: str = None, agency: str = None, limit: int = 10, **kwargs) -> Dict[str, Any]:
        """List schools in an area"""
        return self._search_schools(province=province, district=district, subdistrict=subdistrict,
                                    agency=agency, limit=limit)
    
    def _filter_schools(self, metric: str, operator: str, value: int,
                        province: str = None, district: str = None, 
                        subdistrict: str = None, region: str = None, limit: int = 20, **kwargs) -> Dict[str, Any]:
        """Filter schools by numeric threshold (e.g., schools with < 100 students)"""
        
        # Normalize operator
        operator = operator.lower().strip()
        
        # Handle operator aliases (LLM sometimes sends different formats)
        operator_aliases = {
            "less_than": "lt",
            "<": "lt",
            "lessthan": "lt",
            "greater_than": "gt",
            ">": "gt",
            "greaterthan": "gt",
            "equal": "eq",
            "equals": "eq",
            "==": "eq",
            "=": "eq",
            "less_than_or_equal": "lte",
            "<=": "lte",
            "greater_than_or_equal": "gte",
            ">=": "gte",
        }
        operator = operator_aliases.get(operator, operator)
        
        value = int(value)
        
        # Build filter conditions
        conditions = []
        if region:
            region_provinces = REGIONS.get(region, [])
            if region_provinces:
                 conditions.append(
                     Filter(should=[
                         FieldCondition(key="metadata.province", match=MatchValue(value=p))
                         for p in region_provinces
                     ])
                 )
        elif province:
            province = self._normalize_province(province)
            conditions.append(
                FieldCondition(key="metadata.province", match=MatchValue(value=province))
            )
        if district:
            conditions.append(
                FieldCondition(key="metadata.district", match=MatchText(text=district))
            )
        if subdistrict:
            conditions.append(
                FieldCondition(key="metadata.subdistrict", match=MatchText(text=subdistrict))
            )
        
        scroll_filter = self._build_filter(conditions) if conditions else None
        
        # Fetch schools from schools collection (capped to prevent timeout)
        SCROLL_CAP = 10000
        all_schools = self._scroll_all(self._get_collection("schools"), scroll_filter, limit=SCROLL_CAP)
        capped = len(all_schools) >= SCROLL_CAP
        logger.info(f"DEBUG: _filter_schools fetched {len(all_schools)} schools from DB{' (CAPPED!)' if capped else ''}")
        
        # Determine which field to filter on
        if metric.lower() in ["students", "student", "นักเรียน"]:
            field_name = "total_students"
        elif metric.lower() in ["teachers", "teacher", "ครู", "บุคลากร"]:
            field_name = "total_teachers"
        else:
            field_name = "total_students"
        
        # Apply threshold filter in Python (more flexible than Qdrant numeric filters)
        matching_schools = []
        for r in all_schools:
            meta = r.payload.get("metadata", {})
            count = meta.get(field_name, 0) or 0
            
            # Apply operator
            matches = False
            if operator == "lt" and count < value:
                matches = True
            elif operator == "gt" and count > value:
                matches = True
            elif operator == "eq" and count == value:
                matches = True
            elif operator == "lte" and count <= value:
                matches = True
            elif operator == "gte" and count >= value:
                matches = True
            
            if matches:
                matching_schools.append({
                    "school_name": meta.get("school_name", "ไม่ระบุ"),
                    "province": meta.get("province", ""),
                    "district": meta.get("district", ""),
                    field_name: count,
                    "school_id": meta.get("school_id", ""),
                })
        
        logger.info(f"DEBUG: Found {len(matching_schools)} matching schools after filtering")
        
        # Sort by count (ascending for lt/lte, descending for gt/gte)
        reverse_order = operator in ["gt", "gte"]
        matching_schools.sort(key=lambda x: x.get(field_name, 0), reverse=reverse_order)
        
        # Apply limit
        limited_schools = matching_schools[:limit]
        
        # Human-readable operator
        op_labels = {
            "lt": "น้อยกว่า",
            "gt": "มากกว่า", 
            "eq": "เท่ากับ",
            "lte": "ไม่เกิน",
            "gte": "อย่างน้อย"
        }
        
        # Default summary
        ai_summary = f"พบตามเงื่อนไขทั้งหมด {len(matching_schools)} แห่ง แต่แสดงผลเพียง {len(limited_schools)} แห่ง" + (f" (แสดงครบแล้ว)" if len(matching_schools) == len(limited_schools) else "")
        
        # SMART ANALYSIS: If no results found, analyze why
        if len(matching_schools) == 0:
            total_in_area = len(all_schools)
            if total_in_area > 0:
                # Find max value in this area to give context
                try:
                    max_school = max(all_schools, key=lambda x: x.payload.get("metadata", {}).get(field_name, 0) or 0)
                    max_val = max_school.payload.get("metadata", {}).get(field_name, 0) or 0
                    max_name = max_school.payload.get("metadata", {}).get("school_name", "ไม่ระบุ")
                    
                    metric_label = "นักเรียน" if field_name == "total_students" else "บุคลากร"
                    
                    ai_summary = f"ไม่พบโรงเรียนที่มี{metric_label} {op_labels.get(operator, operator)} {value} คนในพื้นที่นี้ครับ " \
                                 f"(แต่ในพื้นที่นี้มีโรงเรียนทั้งหมด {total_in_area} แห่ง " \
                                 f"ซึ่งสูงสุดคือ {max_name} มี {max_val} คน)"
                except Exception as e:
                    logger.error(f"Error in smart analysis: {e}")
                    ai_summary = "ไม่พบข้อมูลตามเงื่อนไขครับ"
            else:
                 ai_summary = "ไม่พบข้อมูลโรงเรียนในพื้นที่ที่ระบุเลยครับ (อาจสะกดชื่อผิด หรือไม่มีข้อมูลในระบบ)"
                 
                 # SMART FUZZY SUGGESTION
                 # If subdistrict not found, try to find close matches in the same province/district
                 if subdistrict:
                     suggestion = self._get_fuzzy_suggestion(subdistrict, province, district)
                     if suggestion:
                         ai_summary = suggestion
        

        

        
        return {
            "tool": "filter_schools",
            "query": {
                "metric": metric,
                "operator": op_labels.get(operator, operator),
                "value": value,
                "province": province,
                "district": district,
                "subdistrict": subdistrict
            },
            "total_found": len(matching_schools),
            "schools": limited_schools,
            "showing": len(limited_schools),
            "field_name": field_name,
            "ai_summary": ai_summary
        }
    
    # ============================================================
    # PHASE 1: NEW TOOL IMPLEMENTATIONS
    # ============================================================
    
    def _search_education_areas(self, area_name: str = None, province: str = None, 
                                 district: str = None) -> Dict[str, Any]:
        """Search for education areas (สพป./สพม.) with their covered districts"""
        
        # Fetch all education areas first (small dataset ~200 records)
        try:
            results = self._scroll_all(self._get_collection("areas"), None, limit=500)
        except Exception as e:
            logger.warning(f"⚠️ Could not query education areas collection: {e}")
            return {
                "tool": "search_education_areas",
                "query": {"area_name": area_name, "province": province, "district": district},
                "total_found": 0,
                "areas": [],
                "note": "Education areas collection not available"
            }
        
        areas = []
        for r in results:
            meta = r.payload.get("metadata", {})
            area_name_val = meta.get("area_name", "")
            
            # Filter out nan/null values and empty area names
            if not area_name_val or area_name_val == "nan" or str(area_name_val).lower() == "nan":
                continue
            
            # Apply Python-based filtering for better fuzzy matching
            if area_name:
                # Normalize common typos: สพด→สพป, etc.
                search_name = area_name.lower().replace('สพด.', 'สพป.').replace('สพด', 'สพป')
                stored_lower = area_name_val.lower()
                
                # Extract key components for matching
                # For "สพป.เชียงราย เขต 2", extract ["เชียงราย", "เขต 2"] 
                key_parts = []
                if 'เขต' in search_name:
                    # Extract province and district number
                    parts = search_name.replace('สพป.', '').replace('สพม.', '').split()
                    for part in parts:
                        if part and len(part) > 1:
                            key_parts.append(part)
                else:
                    key_parts = [search_name]
                
                # Check if all key parts match
                match = all(part in stored_lower for part in key_parts if part not in ['สพป', 'สพม'])
                if not match and search_name not in stored_lower:
                    continue
            
            if province:
                province_normalized = self._normalize_province(province)
                provinces_list = meta.get("provinces", [])
                text_field = r.payload.get("text", "")
                # Check province in provinces list or in text field
                province_match = any(province_normalized in str(p) for p in provinces_list)
                text_match = province_normalized in text_field
                if not (province_match or text_match):
                    continue
            
            if district:
                districts_list = meta.get("districts_list", [])
                text_field = r.payload.get("text", "")
                # Check district in districts list or in text field
                district_match = any(district in str(d) for d in districts_list)
                text_match = district in text_field
                if not (district_match or text_match):
                    continue
                
            areas.append({
                "area_name": area_name_val,
                "provinces": meta.get("provinces", []),
                "districts_count": meta.get("districts_count", 0),
                "districts_list": meta.get("districts_list", []),
                "school_count": meta.get("school_count", 0),
            })
        
        return {
            "tool": "search_education_areas",
            "query": {"area_name": area_name, "province": province, "district": district},
            "total_found": len(areas),
            "areas": areas
        }
    
    def _get_education_area_info(self, area_name: str, **kwargs) -> Dict[str, Any]:
        """Get information about an education service area including covered districts"""
        if not area_name:
            return {"error": "กรุณาระบุชื่อเขตพื้นที่การศึกษา เช่น สพป.เชียงใหม่ เขต 1"}
        
        # Normalize area_name variations
        normalized = area_name.strip()
        normalized = normalized.replace("สพป ", "สพป.").replace("สพม ", "สพม.")
        normalized = normalized.replace("สพป.", "สพป. ").replace("สพม.", "สพม. ")
        normalized = " ".join(normalized.split())  # Clean up whitespace
        
        logger.info(f"🏫 Searching education area info: {normalized}")
        
        try:
            # Query schools with matching area_name (use contains/partial match)
            results = self.client.scroll(
                collection_name=self._get_collection("schools"),
                limit=2000,
                with_payload=True,
                scroll_filter=models.Filter(
                    should=[
                        models.FieldCondition(
                            key="metadata.area_name",
                            match=models.MatchValue(value=normalized)
                        ),
                        models.FieldCondition(
                            key="metadata.area_name",
                            match=models.MatchValue(value=area_name)
                        ),
                    ]
                )
            )
            
            schools = results[0]
            
            if not schools:
                # Try fuzzy match if exact match fails
                logger.info(f"   No exact match, trying partial search...")
                all_results = self.client.scroll(
                    collection_name=self._get_collection("schools"),
                    limit=5000,
                    with_payload=True
                )
                
                # Filter manually for partial match
                keyword = area_name.replace("สพป.", "").replace("สพม.", "").strip()
                schools = [
                    s for s in all_results[0]
                    if keyword.lower() in (s.payload.get("metadata", {}).get("area_name", "") or "").lower()
                ]
            
            if not schools:
                return {
                    "tool": "get_education_area_info",
                    "error": f"ไม่พบข้อมูลเขตพื้นที่ '{area_name}'"
                }
            
            # Aggregate data
            districts = {}
            province_set = set()
            for s in schools:
                meta = s.payload.get("metadata", s.payload)
                district = meta.get("district", "ไม่ระบุ")
                province_set.add(meta.get("province", ""))
                districts[district] = districts.get(district, 0) + 1
            
            # Sort districts by school count
            sorted_districts = sorted(districts.items(), key=lambda x: -x[1])
            
            # Get actual area_name from data
            actual_area = schools[0].payload.get("metadata", {}).get("area_name", area_name)
            province = list(province_set)[0] if province_set else None
            
            logger.info(f"   Found {len(schools)} schools in {len(districts)} districts")
            
            return {
                "tool": "get_education_area_info",
                "area_name": actual_area,
                "province": province,
                "total_schools": len(schools),
                "total_districts": len(districts),
                "districts": [d[0] for d in sorted_districts],
                "schools_by_district": dict(sorted_districts),
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting education area info: {e}")
            return {"tool": "get_education_area_info", "error": str(e)}
    
    def _get_school_full_details(self, school_name: str, province: str = None, district: str = None, **kwargs) -> Dict[str, Any]:
        """Get full details including GPS, Address, Contact"""
        if not school_name:
            return {"error": "School name is required"}
            
        # 0. DISAMBIGUATION CHECK
        ambiguity_check = self._resolve_school_ambiguity(school_name, province, district=district)
        if ambiguity_check['type'] == 'ambiguous':
             logger.info(f"🤔 Ambiguous school name '{school_name}' -> Found {len(ambiguity_check['choices'])} matches")
             return {
                 "tool": "get_school_full_details",
                 "ambiguous": True,
                 "choices": ambiguity_check['choices'],
                 "query": {"school_name": school_name}
             }
            
        # 1. Try search with provided province (Context-aware)
        results = self._smart_search_school(school_name, province, limit=1)
        
        # 2. if NOT found and province was provided, Try GLOBAL search (Context-ignoring)
        if not results and province:
            logger.info(f"⚠️ School '{school_name}' not found in '{province}'. Retrying GLOBAL search...")
            results = self._smart_search_school(school_name, province=None, limit=1)
        
        if not results:
             # Try to get suggestions
             suggestions = self._suggest_schools(school_name)
             related_summary = None
             if province:
                 try:
                     prov_summary = self._count_schools(province=province)
                     related_summary = {
                         "province": province,
                         "total_schools": prov_summary.get("total_schools", 0),
                         "total_students": prov_summary.get("total_students", 0),
                         "total_teachers": prov_summary.get("total_teachers", 0),
                     }
                 except Exception as e:
                     logger.warning(f"⚠️ [GetSchoolDetails] Related summary failed: {e}")
             return {
                 "tool": "get_school_full_details",
                 "found": False, 
                 "error": "School not found", 
                 "suggestions": suggestions,
                 "related_summary": related_summary
             }

        point = results[0]
        meta = point.payload.get("metadata", {})
        
        # Enrich with detailed student statistics (Phase 2 Requirement)
        school_id = meta.get("school_id")
        student_stats = {}
        if school_id:
            try:
                # Call the new method in SchoolSearchEngine
                student_stats = self.search_engine.get_student_statistics(school_id)
                logger.info(f"📊 Fetched student stats for {school_id}: {len(student_stats.get('by_grade', {}))} grades found")
            except Exception as e:
                logger.error(f"❌ Failed to fetch student stats: {e}")

        final_result = {
            "tool": "get_school_full_details",
            "found": True,
            "school_name": meta.get("school_name"),
            "school_id": meta.get("school_id"),
            "province": meta.get("province"),
            "district": meta.get("district"),
            "subdistrict": meta.get("subdistrict"),
            "postcode": meta.get("postcode", "-"),
            "agency": meta.get("agency"),
            "phone": meta.get("phone", "-"),
            "website": meta.get("website", "-"),
            "lat": meta.get("lat"),
            "lon": meta.get("lon"),
            "google_maps_url": f"https://www.google.com/maps/search/?api=1&query={meta.get('lat')},{meta.get('lon')}" if meta.get('lat') and meta.get('lon') else None,
            "total_students": meta.get("total_students", 0),
            "total_teachers": meta.get("total_teachers", 0),
            "ratio": meta.get("ratio", 0),
            # New fields
            "student_breakdown": student_stats.get("by_grade", {}),
            "student_breakdown_source": student_stats.get("source"),
            
            # New fields: Teacher Breakdown
            "teacher_breakdown": {},
            "teacher_breakdown_source": None
        }
        
        # Enrich with detailed teacher statistics (Feature 12)
        if school_id:
             try:
                 teacher_stats = self.search_engine.get_teacher_statistics(school_id)
                 if teacher_stats:
                     logger.info(f"📊 Fetched teacher stats for {school_id}: {teacher_stats.get('total_teachers')} teachers found")
                     final_result["teacher_breakdown"] = {
                         "by_gender": teacher_stats.get("by_gender"),
                         "by_person_type": teacher_stats.get("by_person_type")
                     }
                     final_result["teacher_breakdown_source"] = teacher_stats.get("source")
             except Exception as e:
                 logger.error(f"❌ Failed to fetch teacher stats: {e}")
                 
        return final_result
    
    def _get_province_summary(self, province: str, **kwargs) -> Dict[str, Any]:
        """Get comprehensive summary of education data for a province"""
        province = self._normalize_province(province)
        
        # Get school count by agency
        school_data = self._count_schools(province=province)
        
        # Get student count
        student_data = self._count_students(province=province)
        
        # Get teacher count with breakdown
        teacher_data = self._count_teachers(province=province)
        
        # Get education areas
        area_data = self._search_education_areas(province=province)
        
        # Get top schools by ratio (best and worst)
        ratio_conditions = [
            FieldCondition(key="metadata.province", match=MatchValue(value=province))
        ]
        ratio_filter = self._build_filter(ratio_conditions)
        ratio_results = self._scroll_all(self._get_collection("ratios"), ratio_filter, limit=100)
        
        # Calculate average ratio
        ratios = [r.payload.get("metadata", {}).get("ratio", 0) for r in ratio_results if r.payload.get("metadata", {}).get("ratio")]
        avg_ratio = sum(ratios) / len(ratios) if ratios else 0
        
        summary = {
            "province": province,
            "schools": {
                "total": school_data.get("total_schools", 0),
                "by_agency": school_data.get("by_agency", {}),
            },
            "students": {
                "total": student_data.get("total_students", 0),
                "by_gender": student_data.get("by_gender", {}),
            },
            "teachers": {
                "total": teacher_data.get("total_teachers", 0),
                "by_gender": teacher_data.get("by_gender", {}),
                "by_person_type": teacher_data.get("by_person_type", {}),
            },
            "education_areas": {
                "total": area_data.get("total_found", 0),
                "areas": [a["area_name"] for a in area_data.get("areas", [])],
            },
            "ratio": {
                "average": round(avg_ratio, 1),
                "schools_with_data": len(ratios),
            }
        }
        
        return {
            "tool": "get_province_summary",
            "query": {"province": province},
            "summary": summary
        }

    # ============================================================
    # PHASE 2: NEW TOOL IMPLEMENTATIONS
    # ============================================================
    
    def _count_by_system_type(self, province: str = None, district: str = None, 
                              system_type: str = None) -> Dict[str, Any]:
        """Count schools by system type (Formal/Informal)"""
        conditions = []
        
        if province:
             province = self._normalize_province(province)
             conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))
        if district:
             conditions.append(FieldCondition(key="metadata.district", match=MatchText(text=district)))
        if system_type:
             conditions.append(FieldCondition(key="metadata.system_type", match=MatchValue(value=system_type)))
             
        scroll_filter = self._build_filter(conditions)
        results = self._scroll_all(self._get_collection("systems"), scroll_filter)
        
        by_system = {}
        total_schools = 0
        
        for r in results:
            meta = r.payload.get("metadata", {})
            sys_type = meta.get("system_type", "ไม่ระบุ")
            # Support both field names: 'count' (new) and 'total_schools' (old)
            count = meta.get("count", meta.get("total_schools", 0))
            
            by_system[sys_type] = by_system.get(sys_type, 0) + count
            total_schools += count
            
        return {
            "tool": "count_by_system_type",
            "query": {"province": province, "district": district, "system_type": system_type},
            "total_schools": total_schools,
            "by_system": by_system
        }
        
    def _analyze_gender_ratio(self, province: str = None, district: str = None, school_name: str = None, **kwargs) -> Dict[str, Any]:
        """Analyze gender distribution of students (Area or Specific School)"""
        
        # 1. School-Specific Delegation
        if school_name:
            # Delegate to the full details tool which already fetches student/teacher breakdowns
            # This avoids code duplication and ensures consistent resolution logic
            logger.info(f"🔄 [AnalyzeGender] Delegating specific school query '{school_name}' to get_school_full_details")
            details = self._get_school_full_details(school_name, province)
            
            if details.get("found"):
                # Construct a compatible response format for gender analysis
                student_breakdown = details.get("student_breakdown", {})
                teacher_breakdown = details.get("teacher_breakdown", {})
                
                # Aggregate totals
                total_male_students = sum(d.get("male", 0) for d in student_breakdown.values())
                total_female_students = sum(d.get("female", 0) for d in student_breakdown.values())
                
                total_male_teachers = teacher_breakdown.get("by_gender", {}).get("male", 0)
                total_female_teachers = teacher_breakdown.get("by_gender", {}).get("female", 0)
                
                return {
                    "tool": "analyze_gender_ratio",
                    "mode": "school_specific",
                    "school_name": details.get("school_name"),
                    "total_students": details.get("total_students", 0),
                    "student_gender": {
                         "male": total_male_students,
                         "female": total_female_students,
                         "ratio": f"{total_male_students}:{total_female_students}" if total_female_students else "N/A"
                    },
                    "teacher_gender": {
                         "male": total_male_teachers,
                         "female": total_female_teachers
                    },
                    "ai_summary": (
                        f"โรงเรียน {details.get('school_name')} มีนักเรียนทั้งหมด {details.get('total_students', 0):,} คน "
                        f"(ชาย {total_male_students:,}, หญิง {total_female_students:,}) "
                        f"และมีครูทั้งหมด {details.get('total_teachers', 0):,} คน "
                        f"(ชาย {total_male_teachers:,}, หญิง {total_female_teachers:,}) "
                        f"ครับ"
                    )
                }
            else:
                 return {
                     "tool": "analyze_gender_ratio",
                     "error": f"School '{school_name}' not found"
                 }

        # 2. Area-Aggregate Path (Existing Logic)
        conditions = []
        
        if province:
             province = self._normalize_province(province)
             conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))
        if district:
             conditions.append(FieldCondition(key="metadata.district", match=MatchText(text=district)))
             
        scroll_filter = self._build_filter(conditions)
        results = self._scroll_all(self._get_collection("gender"), scroll_filter)
        
        total_students = 0
        total_male = 0
        total_female = 0
        subdistricts = []
        
        for r in results:
            meta = r.payload.get("metadata", {})
            
            # Support both old format (male_students/female_students) and new format (gender/count)
            gender = meta.get("gender", "").strip()
            count = meta.get("count", 0)
            
            if gender in ["ชาย", "male", "Male"]:
                total_male += count
                total_students += count
            elif gender in ["หญิง", "female", "Female"]:
                total_female += count
                total_students += count
            else:
                # Fallback to old format
                male = meta.get("male_students", 0)
                female = meta.get("female_students", 0)
                total_male += male
                total_female += female
                total_students += male + female
            
        return {
            "tool": "analyze_gender_ratio",
            "query": {"province": province, "district": district},
            "overview": {
                "total_students": total_students,
                "male": total_male,
                "female": total_female,
                "male_ratio": round((total_male/total_students)*100, 1) if total_students > 0 else 0,
                "female_ratio": round((total_female/total_students)*100, 1) if total_students > 0 else 0,
            }
        }
        
    def _get_grade_distribution(self, province: str = None, district: str = None, 
                                grade: str = None, school_name: str = None) -> Dict[str, Any]:
        """Get student distribution by grade level (School-Specific OR Area-Aggregate)"""
        related_summary = None
        
        # 1. School-Specific Path
        if school_name:
            # Reuse the robust resolution logic (supports Cross-Province / Global Search)
            ambiguity_check = self._resolve_school_ambiguity(school_name, province)
            
            target_school_id = None
            if ambiguity_check['type'] == 'single':
                target_school_id = ambiguity_check['data'].payload.get('metadata', {}).get('school_id')
                logger.info(f"🎯 [GetGradeDist] Resolved school ID: {target_school_id}")
            elif ambiguity_check['type'] == 'ambiguous':
                # Try exact match
                exact = [c for c in ambiguity_check['choices'] if c.get('school_name') == school_name]
                if len(exact) == 1:
                    target_school_id = exact[0].get('school_id')
                    logger.info(f"🎯 [GetGradeDist] Exact match override: {target_school_id}")
            
            if target_school_id:
                # Fetch detailed stats for this school
                stats = self.search_engine.get_student_statistics(target_school_id)
                if stats and "by_grade" in stats:
                     # Convert to standard list format
                     by_grade = stats["by_grade"] # Dict[grade, {total, male, female}]
                     
                     sorted_grades = []
                     # Reuse grade ordering logic if possible or simple sort
                     grade_order = ['อนุบาล 1', 'อนุบาล 2', 'อนุบาล 3', 
                                   'ประถมศึกษาปีที่ 1', 'ประถมศึกษาปีที่ 2', 'ประถมศึกษาปีที่ 3',
                                   'ประถมศึกษาปีที่ 4', 'ประถมศึกษาปีที่ 5', 'ประถมศึกษาปีที่ 6',
                                   'มัธยมศึกษาปีที่ 1', 'มัธยมศึกษาปีที่ 2', 'มัธยมศึกษาปีที่ 3',
                                   'มัธยมศึกษาปีที่ 4', 'มัธยมศึกษาปีที่ 5', 'มัธยมศึกษาปีที่ 6',
                                   'ปวช.1', 'ปวช.2', 'ปวช.3']
                     
                     # Flatten dict to list
                     raw_list = []
                     for g, data in by_grade.items():
                         raw_list.append({"grade": g, "count": data["total"], "male": data["male"], "female": data["female"]})
                         
                     # Sort
                     for g_name in grade_order:
                         found = next((x for x in raw_list if x["grade"] == g_name), None)
                         if found:
                             sorted_grades.append(found)
                             raw_list.remove(found)
                     sorted_grades.extend(raw_list) # Add remaining
                     
                     total = sum(x["count"] for x in sorted_grades)
                     
                     return {
                        "tool": "get_grade_distribution",
                        "query": {"school_name": school_name, "school_id": target_school_id},
                        "total_students": total,
                        "distribution": sorted_grades,
                        "mode": "school_specific"
                     }
                # If no grade breakdown, try to provide related totals for the school
                try:
                    details = self.search_engine.get_school_details(school_name)
                    if details:
                        related_summary = {
                            "school_name": details.get("school_name"),
                            "province": details.get("province"),
                            "district": details.get("district"),
                            "total_students": details.get("total_students", 0),
                            "total_teachers": details.get("total_teachers", 0),
                            "ratio": details.get("ratio", 0)
                        }
                except Exception as e:
                    logger.warning(f"⚠️ [GetGradeDist] Related summary failed: {e}")
            else:
                logger.warning(f"⚠️ [GetGradeDist] School '{school_name}' not resolved. Falling back to area aggregation.")

        # 2. Area-Aggregate Path (Existing Logic)
        conditions = []
        
        if province:
             province = self._normalize_province(province)
             conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))
        if district:
             conditions.append(FieldCondition(key="metadata.district", match=MatchText(text=district)))
        if grade:
             grade = self._normalize_grade(grade)
             
        scroll_filter = self._build_filter(conditions)
        results = self._scroll_all(self._get_collection("grades"), scroll_filter)
        
        grade_counts = {}
        total_students = 0
        
        for r in results:
            meta = r.payload.get("metadata", {})
            # This collection typically has 'grade' and 'count' fields
            # Assuming structure is granular per grade/area
            g = meta.get("grade", "ไม่ระบุ")
            count = meta.get("count", 0) or 0  # Use 'count' field, default to 0 if None
            
            # Filter if specific grade requested
            if grade and g != grade:
                continue
                
            grade_counts[g] = grade_counts.get(g, 0) + count
            total_students += count
            
        # Sort by standard grade order
        # Helper to sort grades
        grade_order = ['อนุบาล 1', 'อนุบาล 2', 'อนุบาล 3', 
                      'ประถมศึกษาปีที่ 1', 'ประถมศึกษาปีที่ 2', 'ประถมศึกษาปีที่ 3',
                      'ประถมศึกษาปีที่ 4', 'ประถมศึกษาปีที่ 5', 'ประถมศึกษาปีที่ 6',
                      'มัธยมศึกษาปีที่ 1', 'มัธยมศึกษาปีที่ 2', 'มัธยมศึกษาปีที่ 3',
                      'มัธยมศึกษาปีที่ 4', 'มัธยมศึกษาปีที่ 5', 'มัธยมศึกษาปีที่ 6',
                      'ปวช.1', 'ปวช.2', 'ปวช.3']
                      
        sorted_grades = []
        for g in grade_order:
            if g in grade_counts:
                sorted_grades.append({"grade": g, "count": grade_counts[g]})
                del grade_counts[g]
        
        # Add remaining
        for g, c in grade_counts.items():
            sorted_grades.append({"grade": g, "count": c})
            
        result = {
            "tool": "get_grade_distribution",
            "query": {"province": province, "district": district, "grade": grade},
            "total_students": total_students,
            "distribution": sorted_grades
        }
        # If no grade distribution found, add a related summary from student totals
        if not sorted_grades:
            try:
                fallback = self._count_students(province=province, district=district)
                related_summary = {
                    "province": province,
                    "district": district,
                    "total_students": fallback.get("total_students", 0),
                    "by_gender": fallback.get("by_gender", {})
                }
            except Exception as e:
                logger.warning(f"⚠️ [GetGradeDist] Fallback totals failed: {e}")

        if related_summary:
            result["related_summary"] = related_summary

        return result

    def _find_best_ratio_schools(self, province: str = None, order: str = "best", 
                                limit: int = 10) -> Dict[str, Any]:
        """Find schools with best/worst student-teacher ratio"""
        conditions = []
        
        if province:
             province = self._normalize_province(province)
             conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))
             
        # For ratio analysis, we need to fetch schools that explicitly have ratio data
        # We can filter for ratio > 0 to avoid DivisionByZero or empty data cases in DB if stored
        conditions.append(FieldCondition(key="metadata.ratio", range=None)) # Just existence check if possible, or handle in python
        
        scroll_filter = self._build_filter(conditions)
        results = self._scroll_all(self._get_collection("ratios"), scroll_filter, limit=5000) # Need more records to sort properly
        
        schools = []
        for r in results:
            meta = r.payload.get("metadata", {})
            ratio = meta.get("ratio", 0)
            
            # Filter valid ratios (e.g. 0 < ratio < 100 to remove outliers/errors)
            if ratio <= 0 or ratio > 100:
                continue
                
            schools.append({
                "school_name": meta.get("school_name"),
                "province": meta.get("province"),
                "ratio": ratio,
                "students": meta.get("total_students", 0),
                "teachers": meta.get("total_teachers", 0)
            })
            
        # Sort
        # Best ratio = LOWEST number (fewer students per teacher)
        # Worst ratio = HIGHEST number (more students per teacher)
        reverse = (order == "worst")
        schools.sort(key=lambda x: x["ratio"], reverse=reverse)
        
        return {
            "tool": "find_best_ratio_schools",
            "query": {"province": province, "order": order},
            "schools": schools[:int(limit)]
        }

    # ============================================================
    # PHASE 3: NEW TOOL IMPLEMENTATIONS
    # ============================================================
    
    def _analyze_teacher_distribution(self, province: str = None, district: str = None,
                                      region: str = None, person_type: str = None,
                                      gender: str = None) -> Dict[str, Any]:
        """Analyze teacher distribution by person type, optionally filtered by gender"""
        conditions = []
        
        if person_type:
            person_type = self._normalize_person_type(person_type)
        
        # Normalize gender
        if gender:
            gender_map = {
                'ชาย': 'ชาย', 'male': 'ชาย', 'ผู้ชาย': 'ชาย', 'm': 'ชาย',
                'หญิง': 'หญิง', 'female': 'หญิง', 'ผู้หญิง': 'หญิง', 'f': 'หญิง',
            }
            gender = gender_map.get(gender.strip().lower(), gender.strip())
            if gender in ('ชาย', 'หญิง'):
                conditions.append(FieldCondition(key="metadata.gender", match=MatchValue(value=gender)))
        
        if province:
            province = self._normalize_province(province)
            conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))
        if district:
            conditions.append(FieldCondition(key="metadata.district", match=MatchText(text=district)))

        if region:
            region = self._normalize_region(region)
            if region:
                region_provinces = REGIONS.get(region, [])
                if region_provinces:
                    province_conditions = [
                        FieldCondition(key="metadata.province", match=MatchValue(value=prov))
                        for prov in region_provinces
                    ]
                    conditions.append(Filter(should=province_conditions))
            
        scroll_filter = self._build_filter(conditions)
        results = self._scroll_all(self._get_collection("teachers"), scroll_filter)
        
        type_counts = {}
        total = 0
        male_total = 0
        female_total = 0
        
        for r in results:
            meta = r.payload.get("metadata", {})
            ptype = meta.get("person_type", "ไม่ระบุ")
            count = meta.get("count", 0)
            gender = meta.get("gender", "")
            
            # Filter by person_type if specified
            if person_type and ptype != person_type:
                continue
                
            if ptype not in type_counts:
                type_counts[ptype] = {"total": 0, "male": 0, "female": 0}
            type_counts[ptype]["total"] += count
            
            if gender == "ชาย":
                type_counts[ptype]["male"] += count
                male_total += count
            elif gender == "หญิง":
                type_counts[ptype]["female"] += count
                female_total += count
            total += count
            
        # Sort by count
        sorted_types = sorted(type_counts.items(), key=lambda x: x[1]["total"], reverse=True)
        
        return {
            "tool": "analyze_teacher_distribution",
            "query": {"province": province, "district": district, "region": region, "person_type": person_type, "gender": gender},
            "total_teachers": total,
            "by_gender": {"male": male_total, "female": female_total},
            "by_type": [{"type": t, "total": v["total"], "male": v["male"], "female": v["female"]} 
                       for t, v in sorted_types]
        }
    
    def _ranking_by_agency(self, province: str = None, metric: str = "schools",
                          limit: int = 10) -> Dict[str, Any]:
        """Rank agencies by schools/students/teachers count"""
        conditions = []
        
        if province:
            province = self._normalize_province(province)
            conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))
            
        # Use schools collection for counting
        scroll_filter = self._build_filter(conditions)
        results = self._scroll_all(self._get_collection("schools"), scroll_filter)
        
        agency_counts = {}
        
        for r in results:
            meta = r.payload.get("metadata", {})
            agency = meta.get("agency", "ไม่ระบุสังกัด")
            
            if agency not in agency_counts:
                agency_counts[agency] = 0
            agency_counts[agency] += 1
            
        # Sort and take top N
        sorted_agencies = sorted(agency_counts.items(), key=lambda x: x[1], reverse=True)[:int(limit)]
        
        return {
            "tool": "ranking_by_agency",
            "query": {"province": province, "metric": metric, "limit": limit},
            "ranking": [{"rank": i+1, "agency": a, "count": c} for i, (a, c) in enumerate(sorted_agencies)]
        }
    
    def _ranking_subdistricts(self, province: str, district: str = None,
                             metric: str = "schools", order: str = "most",
                             limit: int = 10) -> Dict[str, Any]:
        """Rank subdistricts by schools/students/teachers count"""
        conditions = []
        
        province = self._normalize_province(province)
        conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))
        
        if district:
            conditions.append(FieldCondition(key="metadata.district", match=MatchText(text=district)))
            
        scroll_filter = self._build_filter(conditions)
        results = self._scroll_all(self._get_collection("schools"), scroll_filter)
        
        subdistrict_counts = {}
        
        for r in results:
            meta = r.payload.get("metadata", {})
            sub = meta.get("subdistrict", meta.get("sub_district", "ไม่ระบุ"))
            
            if sub not in subdistrict_counts:
                subdistrict_counts[sub] = 0
            subdistrict_counts[sub] += 1
            
        # Sort
        reverse = (order == "most")
        sorted_subs = sorted(subdistrict_counts.items(), key=lambda x: x[1], reverse=reverse)[:int(limit)]
        
        return {
            "tool": "ranking_subdistricts",
            "query": {"province": province, "district": district, "metric": metric, "order": order},
            "ranking": [{"rank": i+1, "subdistrict": s, "count": c} for i, (s, c) in enumerate(sorted_subs)]
        }
    
    def _get_district_summary(self, province: str, district: str, **kwargs) -> Dict[str, Any]:
        """Get comprehensive summary for a district"""
        province = self._normalize_province(province)
        
        # Count schools
        school_conditions = [
            FieldCondition(key="metadata.province", match=MatchValue(value=province)),
            FieldCondition(key="metadata.district", match=MatchText(text=district))
        ]
        school_filter = self._build_filter(school_conditions)
        schools = self._scroll_all(self._get_collection("schools"), school_filter)
        
        # Count subdistricts and agencies
        subdistricts = set()
        agencies = {}
        
        for r in schools:
            meta = r.payload.get("metadata", {})
            sub = meta.get("subdistrict", meta.get("sub_district", ""))
            if sub:
                subdistricts.add(sub)
            agency = meta.get("agency", "ไม่ระบุ")
            agencies[agency] = agencies.get(agency, 0) + 1
            
        # Count students
        student_filter = self._build_filter(school_conditions)
        students = self._scroll_all(self._get_collection("students"), student_filter)
        total_students = sum(r.payload.get("metadata", {}).get("count", 0) for r in students)
        
        # Count teachers
        teacher_filter = self._build_filter(school_conditions)
        teachers = self._scroll_all(self._get_collection("teachers"), teacher_filter)
        total_teachers = sum(r.payload.get("metadata", {}).get("count", 0) for r in teachers)
        
        return {
            "tool": "get_district_summary",
            "query": {"province": province, "district": district},
            "summary": {
                "total_schools": len(schools),
                "total_students": total_students,
                "total_teachers": total_teachers,
                "num_subdistricts": len(subdistricts),
                "subdistricts": list(subdistricts)[:10],
                "by_agency": [{"agency": a, "count": c} for a, c in sorted(agencies.items(), key=lambda x: x[1], reverse=True)]
            }
        }
    
    def _compare_provinces(self, provinces: str, metrics: str = "all", **kwargs) -> Dict[str, Any]:
        """Compare education data between multiple provinces"""
        province_list = [p.strip() for p in provinces.split(",")]
        results = []
        
        for prov in province_list:
            prov = self._normalize_province(prov)
            
            # Get school count
            school_filter = self._build_filter([
                FieldCondition(key="metadata.province", match=MatchValue(value=prov))
            ])
            schools = self._scroll_all(self._get_collection("schools"), school_filter)
            
            # Get student count
            student_filter = school_filter
            students = self._scroll_all(self._get_collection("students"), student_filter)
            total_students = sum(r.payload.get("metadata", {}).get("count", 0) for r in students)
            
            # Get teacher count
            teacher_filter = school_filter
            teachers = self._scroll_all(self._get_collection("teachers"), teacher_filter)
            total_teachers = sum(r.payload.get("metadata", {}).get("count", 0) for r in teachers)
            
            # Calculate ratio
            ratio = round(total_students / total_teachers, 1) if total_teachers > 0 else 0
            
            results.append({
                "province": prov,
                "schools": len(schools),
                "students": total_students,
                "teachers": total_teachers,
                "ratio": ratio
            })
            
        return {
            "tool": "compare_provinces",
            "query": {"provinces": provinces, "metrics": metrics},
            "comparison": results
        }
    
    def _compare_years(self, year1: str, year2: str, province: str = None,
                       school_name: str = None, metric: str = "all", **kwargs) -> Dict[str, Any]:
        """Compare education data between 2 years"""
        from .constants import YEAR_ALIASES, YEAR_COLLECTIONS, V5_YEAR, AVAILABLE_YEARS, COLLECTION_NAMES
        
        # Normalize years
        y1 = str(year1).strip()
        y2 = str(year2).strip()
        y1 = YEAR_ALIASES.get(y1, y1)
        y2 = YEAR_ALIASES.get(y2, y2)
        
        logger.info(f"📅 [CompareYears] Comparing year {y1} vs {y2}, province={province}, school={school_name}, metric={metric}")
        
        # Check availability
        for y in [y1, y2]:
            if y not in AVAILABLE_YEARS:
                return {
                    "tool": "compare_years",
                    "error": f"ไม่มีข้อมูลปี {y} ในระบบ (มีเฉพาะปี {', '.join(AVAILABLE_YEARS)})",
                    "available_years": AVAILABLE_YEARS,
                }
        
        def get_collections_for_year(year: str) -> Dict[str, str]:
            """Get collection names for a specific year"""
            if year == V5_YEAR:
                # v5 = 2568 = latest
                return COLLECTION_NAMES.copy()
            elif year in YEAR_COLLECTIONS:
                return YEAR_COLLECTIONS[year]
            else:
                return {}
        
        def get_year_data(year: str) -> Dict[str, Any]:
            """Fetch all metrics for a given year"""
            colls = get_collections_for_year(year)
            if not colls:
                return {"error": f"ไม่มี collection สำหรับปี {year}"}
            
            conditions = []
            
            # Province filter
            if province:
                prov = self._normalize_province(province)
                conditions.append(
                    FieldCondition(key="metadata.province", match=MatchValue(value=prov))
                )
            
            # School filter
            resolved_school_id = None
            if school_name:
                ambiguity = self._resolve_school_ambiguity(school_name, province)
                if ambiguity['type'] == 'single':
                    resolved_school_id = ambiguity['data'].payload.get('metadata', {}).get('school_id')
                elif ambiguity['type'] == 'ambiguous':
                    exact = [c for c in ambiguity['choices'] if c.get('school_name') == school_name]
                    if len(exact) == 1:
                        resolved_school_id = exact[0].get('school_id')
                    else:
                        return {
                            "ambiguous": True,
                            "choices": ambiguity['choices'],
                        }
                
                if resolved_school_id:
                    conditions.append(
                        FieldCondition(key="metadata.school_id", match=MatchValue(value=str(resolved_school_id)))
                    )
                elif school_name:
                    sn, _ = self._normalize_school_name(school_name)
                    conditions.append(
                        FieldCondition(key="metadata.school_name", match=MatchText(text=sn))
                    )
            
            scroll_filter = self._build_filter(conditions) if conditions else None
            
            data = {}
            
            # Schools count
            if metric in ["all", "schools"]:
                try:
                    schools_coll = colls.get("schools", "")
                    if schools_coll:
                        schools = self._scroll_all(schools_coll, scroll_filter, limit=200000)
                        data["schools"] = len(schools)
                    else:
                        data["schools"] = 0
                except Exception as e:
                    logger.warning(f"⚠️ [CompareYears] Error fetching schools for {year}: {e}")
                    data["schools"] = 0
            
            # Students count
            if metric in ["all", "students", "ratio"]:
                try:
                    students_coll = colls.get("students", "")
                    if students_coll:
                        students = self._scroll_all(students_coll, scroll_filter, limit=200000)
                        total = sum(r.payload.get("metadata", {}).get("count", 0) for r in students)
                        data["students"] = total
                    else:
                        data["students"] = 0
                except Exception as e:
                    logger.warning(f"⚠️ [CompareYears] Error fetching students for {year}: {e}")
                    data["students"] = 0
            
            # Teachers count
            if metric in ["all", "teachers", "ratio"]:
                try:
                    teachers_coll = colls.get("teachers", "")
                    if teachers_coll:
                        teachers = self._scroll_all(teachers_coll, scroll_filter, limit=200000)
                        total = sum(r.payload.get("metadata", {}).get("count", 0) for r in teachers)
                        data["teachers"] = total
                    else:
                        data["teachers"] = 0
                except Exception as e:
                    logger.warning(f"⚠️ [CompareYears] Error fetching teachers for {year}: {e}")
                    data["teachers"] = 0
            
            # Ratio
            if metric in ["all", "ratio"]:
                if data.get("teachers", 0) > 0 and data.get("students", 0) > 0:
                    data["ratio"] = round(data["students"] / data["teachers"], 1)
                else:
                    data["ratio"] = 0
            
            return data
        
        # Fetch data for both years
        data1 = get_year_data(y1)
        data2 = get_year_data(y2)
        
        # Calculate differences
        diff = {}
        for key in ["schools", "students", "teachers", "ratio"]:
            if key in data1 and key in data2:
                val1 = data1[key]
                val2 = data2[key]
                change = val2 - val1
                pct = round((change / val1) * 100, 1) if val1 > 0 else 0
                diff[key] = {
                    "change": change,
                    "percent_change": pct,
                    "direction": "เพิ่มขึ้น" if change > 0 else "ลดลง" if change < 0 else "เท่าเดิม"
                }
        
        scope = "ทั้งประเทศ"
        if school_name:
            scope = f"โรงเรียน{school_name}"
        elif province:
            scope = f"จังหวัด{province}"
        
        return {
            "tool": "compare_years",
            "scope": scope,
            "year1": {"year": y1, "data": data1},
            "year2": {"year": y2, "data": data2},
            "difference": diff,
            "metric": metric,
            "guidance": f"REQUIRED: สรุปการเปรียบเทียบข้อมูลปี {y1} กับ {y2} อย่างชัดเจน ระบุตัวเลข จำนวนที่เปลี่ยนแปลง และ % ที่เปลี่ยนแปลง"
        }
    
    def _find_nearby_schools(self, latitude: float, longitude: float,
                            radius_km: float = 5, limit: int = 10) -> Dict[str, Any]:
        """Find schools near GPS coordinates using Haversine distance"""
        import math
        
        # Convert to float
        lat = float(latitude)
        lon = float(longitude)
        radius = float(radius_km)
        
        # Fetch all schools (we'll filter by distance in Python since Qdrant doesn't support geo queries on flat collections)
        results = self._scroll_all(self._get_collection("schools"), None, limit=10000)
        
        def haversine(lat1, lon1, lat2, lon2):
            """Calculate distance between two points in km"""
            R = 6371  # Earth radius in km
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
            c = 2 * math.asin(math.sqrt(a))
            return R * c
        
        nearby = []
        for r in results:
            meta = r.payload.get("metadata", {})
            school_lat = meta.get("lat", meta.get("latitude", 0))
            school_lon = meta.get("lon", meta.get("longitude", 0))
            
            if not school_lat or not school_lon:
                continue
                
            try:
                dist = haversine(lat, lon, float(school_lat), float(school_lon))
                if dist <= radius:
                    nearby.append({
                        "school_name": meta.get("school_name"),
                        "province": meta.get("province"),
                        "district": meta.get("district"),
                        "distance_km": round(dist, 2),
                        "lat": school_lat,
                        "lon": school_lon
                    })
            except:
                continue
                
        # Sort by distance
        nearby.sort(key=lambda x: x["distance_km"])
        
        return {
            "query": {"latitude": lat, "longitude": lon, "radius_km": radius},
            "schools": nearby[:int(limit)]
        }


        
    def _unused_filter_schools_duplicate(self, metric: str, operator: str, value: float,
                       province: str = None, district: str = None, 
                       subdistrict: str = None, limit: int = 20) -> Dict[str, Any]:
        """Filter schools by condition (e.g. students > 100)"""
        conditions = []
        
        # Map metric to field
        field_map = {
            "students": "metadata.total_students",
            "teachers": "metadata.total_teachers"
        }
        field = field_map.get(metric)
        if not field:
            return {"error": f"Unknown metric: {metric}"}
            
        # Map operator to Range
        val = float(value)
        r = None
        if operator == "gt": r = Range(gt=val)
        elif operator == "gte": r = Range(gte=val)
        elif operator == "lt": r = Range(lt=val)
        elif operator == "lte": r = Range(lte=val)
        elif operator == "eq": r = Range(gte=val, lte=val)
        
        if r:
            conditions.append(FieldCondition(key=field, range=r))
            
        # Location filters
        if province:
            province = self._normalize_province(province)
            conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))
        if district:
            conditions.append(FieldCondition(key="metadata.district", match=MatchText(text=district)))
        if subdistrict:
            conditions.append(FieldCondition(key="metadata.subdistrict", match=MatchText(text=subdistrict)))
            
        scroll_filter = self._build_filter(conditions)
        results = self._scroll_all(self._get_collection("schools"), scroll_filter, limit=limit)
        
        return {
            "tool": "filter_schools",
            "query": {
                "metric": metric, "operator": operator, "value": value,
                "province": province
            },
            "total_found": len(results),
            "schools": [
                {
                    "school_name": r.payload.get("metadata", {}).get("school_name"),
                    "province": r.payload.get("metadata", {}).get("province"),
                    "district": r.payload.get("metadata", {}).get("district"),
                    "value": r.payload.get("metadata", {}).get("total_students") if metric == "students" else r.payload.get("metadata", {}).get("total_teachers")
                }
                for r in results
            ]
        }

    def _get_fuzzy_suggestion(self, subdistrict: str, province: str = None, district: str = None) -> str:
        """Helper to find fuzzy matches for a missing subdistrict"""
        if not subdistrict:
            return ""
            
        try:
            candidates = set()
            # Scope: If district is known, search in district. Else if province known, in province.
            if district or province:
                scope_prov = province
                scope_dist = district
                
                # Build simplified filter for scope
                scope_conditions = []
                if scope_prov:
                    scope_conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=self._normalize_province(scope_prov))))
                if scope_dist:
                    scope_conditions.append(FieldCondition(key="metadata.district", match=MatchText(text=scope_dist)))
                
                scope_filter = self._build_filter(scope_conditions) if scope_conditions else None
                
                # Fetch raw schools with payload using _scroll_all
                raw_candidates = self._scroll_all(self._get_collection("schools"), scope_filter, limit=200)
                
                for s in raw_candidates:
                    s_sub = s.payload.get("metadata", {}).get("subdistrict")
                    if s_sub:
                        candidates.add(s_sub)
                        
                # Fuzzy match
                if candidates:
                    matches = difflib.get_close_matches(subdistrict, candidates, n=1, cutoff=0.6)
                    if matches:
                        suggested = matches[0]
                        return f"ไม่พบข้อมูลในตำบล '{subdistrict}' ครับ คาดว่าน่าจะเป็น **'{suggested}'** " \
                               f"(ต้องการให้ค้นหาใน '{suggested}' แทนไหมครับ?)"
        except Exception as ex:
            logger.error(f"Fuzzy suggestion helper failed: {ex}")
            
        return ""
