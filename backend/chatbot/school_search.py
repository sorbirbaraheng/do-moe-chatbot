"""
School Search Engine for Education Chatbot
Handles school-specific searches by name, province, district
"""

import logging
from typing import List, Dict, Optional, Tuple, Any
from difflib import SequenceMatcher

from rapidfuzz import process, fuzz

import google.generativeai as genai
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range, ScoredPoint

from .constants import COLLECTIONS, PRIMARY_COLLECTION
from .thai_provinces import THAI_PROVINCES

logger = logging.getLogger(__name__)


class SchoolSearchEngine:
    """Search engine for education data collection"""
    
    
    def __init__(self, client: QdrantClient, llm_provider=None):
        self.client = client
        self.llm_provider = llm_provider
        # Use unified collection (thailand_education) for all queries
        self.collection = PRIMARY_COLLECTION
        
        # In-Memory Cache for Global Fuzzy Search (Loaded lazily)
        self._school_names_cache = [] 
        self._cache_loaded = False
        self._cache_lock = None  # Lazy init to avoid pickling issues if any
        
    def _ensure_cache_lock(self):
        import threading
        if self._cache_lock is None:
            self._cache_lock = threading.Lock()
            
    def _load_school_names_cache(self):
        """Load minimal school data into memory for global fuzzy search"""
        self._ensure_cache_lock()
        with self._cache_lock:
            if self._cache_loaded:
                return

            logger.info("💾 Loading school names into memory cache for global fuzzy search...")
            try:
                # Scroll all schools (approx 30k - fast enough)
                offset = None
                while True:
                    response = self.client.scroll(
                        collection_name=self.collection,
                        scroll_filter=None,
                        limit=5000,
                        offset=offset,
                        with_payload=True,
                        with_vectors=False
                    )
                    
                    points, next_offset = response
                    
                    for p in points:
                        meta = p.payload.get('metadata', {})
                        name = meta.get('school_name')
                        if name:
                            self._school_names_cache.append({
                                'name': name,
                                'province': meta.get('province'),
                                'id': p.id,
                                'payload': p.payload
                            })
                            
                    offset = next_offset
                    if offset is None:
                        break
                        
                self._cache_loaded = True
                logger.info(f"✅ Loaded {len(self._school_names_cache)} schools into memory.")
                
            except Exception as e:
                logger.error(f"Failed to load school cache: {e}")

    def _normalize_name(self, name: str) -> str:
        """
        Normalize school name for consistent matching
        - Remove spaces
        - Remove common prefixes
        - Convert Thai numerals
        - Fix common typos
        """
        if not name: return ""
        name = name.strip()
        
        # NEW: Handle specific prefixes before normalization
        prefixes = ["โรงเรียน", "ร.ร.", "รร.", "วิทยาลัย", "มหาวิทยาลัย", "ศูนย์", "มูลนิธิ"]
        for p in prefixes:
            if name.startswith(p):
                name = name[len(p):].strip()
                break # Remove only the first matching prefix
        
        # Existing normalization logic continues...
        name = name.replace("อนุบาน", "อนุบาล")
        name = name.replace("วิทยลัย", "วิทยาลัย")
        name = name.replace("เชียงหม่", "เชียงใหม่")
            
        # 1. Convert Thai numerals
        thai_digits = "๐๑๒๓๔๕๖๗๘๙"
        arabic_digits = "0123456789"
        trans = str.maketrans(thai_digits, arabic_digits)
        name = name.translate(trans)
        
        # 2. Remove common prefixes
        prefixes = ["โรงเรียน", "รร.", "ร.ร.", "รร ", "ร.ร. "]
        for p in prefixes:
            if name.startswith(p):
                name = name[len(p):]
                break # Only remove one prefix
                
        # 3. Remove all whitespace
        name = name.replace(" ", "")
        
        return name

    def search_by_name(self, name: str, limit: int = 10) -> List:
        """Search schools by name - try text match first, then semantic search, then fuzzy search"""
        results = []
        
        def deduplicate(items, target_limit):
            """Helper to deduplicate by school_code"""
            seen_keys = set()
            unique = []
            for item in items:
                payload = item.payload.get('metadata', {}) if hasattr(item, 'payload') else {}
                code = payload.get('school_id')
                name = payload.get('school_name', '')
                province = payload.get('province', '')
                
                # Use ID if available, otherwise use name+province
                key = code if code else f"{name}_{province}"
                
                if key and key not in seen_keys:
                    seen_keys.add(key)
                    unique.append(item)
                    if len(unique) >= target_limit:
                        break
            return unique
        
        # 1. Try text-match filter first (Exact & Normalized)
        try:
            # 1a. Try EXACT text-match filter first
            response = self.client.scroll(
                collection_name=self.collection,
                scroll_filter=Filter(must=[
                    FieldCondition(key="metadata.school_name", match=MatchValue(value=name))
                ]),
                limit=limit * 5,
                with_payload=True
            )
            results = deduplicate(response[0], limit)
            
            # 1b. If no exact match, try NORMALIZED text match (strip space, prefix, numerals)
            if not results:
                norm_name = self._normalize_name(name)
                if norm_name and norm_name != name:
                    logger.info(f"Retrying with normalized name: '{norm_name}'")
                    pass 
            
            if results:
                logger.info(f"🏫 Text match found {len(results)} unique schools for '{name}'")
                return results
        except Exception as e:
            logger.warning(f"Text match failed: {e}")
        
        # 2. Try Semantic Search
        try:
            # Use normalized name for semantic search to reduce noise
            search_query = f"โรงเรียน{self._normalize_name(name)}"
            
            if self.llm_provider:
                query_vector = self.llm_provider.embed_content(search_query)
            else:
                # Legacy fallback
                result = genai.embed_content(
                    model="models/text-embedding-004",
                    content=search_query,
                    task_type="retrieval_query"
                )
                query_vector = result['embedding']
            
            if not query_vector:
                # Fallback to fuzzy if embedding fails
                 logger.warning("Empty embedding vector, skipping semantic search")
            else:
                response = self.client.query_points(
                    collection_name=self.collection,
                    query=query_vector,
                    # Higher similarity threshold to avoid wildly unrelated semantic matches
                    # Bumped to 0.82 to force Fuzzy Search for typos
                    score_threshold=0.82, 
                    limit=limit * 5,
                    with_payload=True
                )
                results = response.points
                unique_results = deduplicate(results, limit)
                
                if unique_results:
                    logger.info(f"🔍 Semantic search found {len(unique_results)} schools for '{name}'")
                    return unique_results
                
        except Exception as e:
            logger.error(f"Semantic search error: {e}")

        # 3. Fallback: Fuzzy Search (Typo Tolerance)
        # Only triggered if Exact Match and Semantic Search (with high threshold) failed
        try:
            logger.info(f"🧩 Trying Fuzzy Search for '{name}'...")
            return self.find_similar_schools_fuzzy(name, limit=limit)
        except Exception as e:
            logger.error(f"Fuzzy search fallback error: {e}")
            return []

    def find_similar_schools_fuzzy(self, query_name: str, limit: int = 5, threshold: int = 60):
        """
        Perform fuzzy search on school names using RapidFuzz.
        Strategy:
        1. Extract province from query if present.
        2. If province found: Fetch ALL schools in that province and fuzzy match. (Very accurate)
        3. If no province: Use In-Memory Cache for Global Fuzzy Search.
        """
        try:
            # Check if query contains province in Thai provinces list
            province = None
            norm_name = self._normalize_name(query_name)
            
            for prov in THAI_PROVINCES:
                if prov in query_name:
                    province = prov
                    # Remove province from query for better name matching
                    query_name = query_name.replace(prov, "").strip()
                    norm_name = self._normalize_name(query_name)
                    break
            
            candidates = []
            
            if province:
                # Step 2: Fetch all schools in province
                logger.info(f"🧩 Fuzzy search in province: {province}")
                try:
                    response = self.client.scroll(
                        collection_name=self.collection,
                        scroll_filter=Filter(
                            must=[FieldCondition(key="metadata.province", match=MatchValue(value=province))]
                        ),
                        limit=1000, # Should cover most schools in a province
                        with_payload=True,
                        with_vectors=False
                    )
                    
                    raw_candidates = response[0]
                    
                    # RapidFuzz logic for province scope
                    # Extract school names
                    choices = [p.payload.get('metadata', {}).get('school_name', '') for p in raw_candidates]
                    
                    # Use RapidFuzz extract
                    matches = process.extract(
                        norm_name,
                        choices,
                        limit=limit * 3, # Get more candidates since we use WRatio
                        scorer=fuzz.WRatio,
                        processor=self._normalize_name 
                    )
                    
                    for name, score, idx in matches:
                        if score >= threshold:
                            p = raw_candidates[idx]
                            candidates.append(ScoredPoint(
                                id=p.id,
                                version=0,
                                score=score / 100.0,
                                payload=p.payload,
                                vector=None
                            ))
                            
                except Exception as e:
                    logger.error(f"Error fetching schools in province {province}: {e}")
                    return []
                        
            else:
                # Step 3: No province - Use In-Memory Cache for Global Fuzzy Search
                self._load_school_names_cache()
                
                if not self._school_names_cache:
                    return []

                logger.info(f"🧩 Global Fuzzy Search in memory ({len(self._school_names_cache)} schools)...")
                
                # Extract cache names for matching
                cache_names = [s['name'] for s in self._school_names_cache]
                
                matches = process.extract(
                    norm_name,
                    cache_names,
                    limit=limit * 2, # Get more candidates to filter by threshold
                    scorer=fuzz.WRatio,
                    processor=self._normalize_name
                )
                
                for name, score, idx in matches:
                    if score >= threshold:
                        cached_item = self._school_names_cache[idx]
                        # Create ScoredPoint-like object
                        candidates.append(ScoredPoint(
                            id=cached_item['id'],
                            version=0,
                            score=score / 100.0,
                            payload=cached_item['payload'],
                            vector=None
                        ))

            logger.info(f"🧩 Fuzzy search matched {len(candidates)} candidates")
            return candidates[:limit]

        except Exception as e:
            logger.error(f"Fuzzy internal error: {e}")
            return []

    def find_similar_schools(self, query: str, province: str = None, top_k: int = 5, threshold: float = 0.5) -> List[Dict]:
        """Find school names similar to query using fuzzy matching"""
        try:
            conditions = []
            if province:
                conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))
            
            scroll_filter = Filter(must=conditions) if conditions else None
            
            response = self.client.scroll(
                collection_name=self.collection,
                scroll_filter=scroll_filter,
                limit=500,
                with_payload=["metadata.school_name", "metadata.province", "metadata.district"]
            )
            
            all_schools = response[0]
            if not all_schools:
                return []
            
            scored_schools = []
            query_lower = query.lower()
            
            for school in all_schools:
                meta = school.payload.get('metadata', {})
                school_name = meta.get('school_name', '')
                if not school_name:
                    continue
                    
                ratio = SequenceMatcher(None, query_lower, school_name.lower()).ratio()
                
                if query_lower in school_name.lower() or school_name.lower() in query_lower:
                    ratio = max(ratio, 0.7)
                
                if ratio >= threshold:
                    scored_schools.append({
                        'name': school_name,
                        'province': meta.get('province', '-'),
                        'district': meta.get('district', '-'),
                        'score': ratio
                    })
            
            scored_schools.sort(key=lambda x: x['score'], reverse=True)
            logger.info(f"🔤 Found {len(scored_schools)} similar schools for '{query}'")
            return scored_schools[:top_k]
            
        except Exception as e:
            logger.error(f"Fuzzy school search error: {e}")
            return []
    
    def search_by_province(self, province: str, agency: str = None, limit: int = 20) -> List:
        """List schools in a province, optionally filtered by agency"""
        conditions = [
            FieldCondition(key="metadata.province", match=MatchValue(value=province))
        ]
        if agency:
            conditions.append(
                FieldCondition(key="metadata.agency", match=MatchValue(value=agency))
            )
        
        try:
            response = self.client.scroll(
                collection_name=self.collection,
                scroll_filter=Filter(must=conditions),
                limit=limit * 5,
                with_payload=True
            )
            
            seen_keys = set()
            unique_results = []
            for point in response[0]:
                meta = point.payload.get('metadata', {})
                code = meta.get('school_id')
                name = meta.get('school_name', '')
                # Fallback key
                key = code if code else f"{name}_{meta.get('province','')}"
                
                if key and key not in seen_keys:
                    seen_keys.add(key)
                    unique_results.append(point)
                    if len(unique_results) >= limit:
                        break
            
            return unique_results
        except Exception as e:
            logger.error(f"School search by province error: {e}")
            return []
    
    def search_by_district(self, province: str, district: str, agency: str = None, limit: int = 20) -> List:
        """List schools in a district with robust name matching"""
        
        base_district = district.replace('อำเภอ', '').replace('อ.', '').strip()
        
        district_variants = {
            base_district,
            f"{base_district}{province}",
            f"อำเภอ{base_district}",
            f"อำเภอ{base_district}{province}",
            f"อ.{base_district}",
            f"อ.{base_district}{province}"
        }
            
        logger.info(f"🔎 Searching district variations for '{district}': {list(district_variants)}")

        district_should = [
            FieldCondition(key="metadata.district", match=MatchValue(value=d))
            for d in district_variants
        ]
        
        conditions = [
            FieldCondition(key="metadata.province", match=MatchValue(value=province)),
            Filter(should=district_should)
        ]
        
        if agency:
            conditions.insert(0, FieldCondition(key="metadata.agency", match=MatchValue(value=agency)))
        
        try:
            response = self.client.scroll(
                collection_name=self.collection,
                scroll_filter=Filter(must=conditions),
                limit=limit * 5,
                with_payload=True
            )
            
            seen_keys = set()
            unique_results = []
            for point in response[0]:
                meta = point.payload.get('metadata', {})
                code = meta.get('school_id')
                name = meta.get('school_name', '')
                # Fallback key
                key = code if code else f"{name}_{meta.get('province','')}"
                
                if key and key not in seen_keys:
                    seen_keys.add(key)
                    unique_results.append(point)
                    if len(unique_results) >= limit:
                        break
            
            
            return unique_results
        except Exception as e:
            logger.error(f"School search by district error: {e}")
            return []

    
    def search_by_criteria(self, filters: Dict[str, Any], limit: int = 15, offset: Any = None) -> Tuple[List, int, Any]:
        """
        Advanced search with multiple strict filters.
        Returns: (results, total_count, next_offset)
        """
        conditions = []
        
        # 1. Location Filters
        if filters.get('province'):
            conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=filters['province'])))
        if filters.get('district'):
            base_dist = filters['district'].replace('อำเภอ', '').replace('อ.', '').strip()
            # Strict or fuzzy? For filters, strict match on variants might be safer or just simple match
            # Let's try simple match first, relying on parser to normalize
            conditions.append(FieldCondition(key="metadata.district", match=MatchValue(value=filters['district']))) 
        if filters.get('subdistrict'):
            conditions.append(FieldCondition(key="metadata.subdistrict", match=MatchValue(value=filters['subdistrict'])))
            
        # 2. Agency/Area Filters
        if filters.get('agency'):
            conditions.append(FieldCondition(key="metadata.agency", match=MatchValue(value=filters['agency'])))
        if filters.get('area_name'):
             conditions.append(FieldCondition(key="metadata.area_name", match=MatchValue(value=filters['area_name'])))
             
        # 3. Numeric Filters (Range)
        if filters.get('min_students') is not None or filters.get('max_students') is not None:
            range_params = {}
            if filters.get('min_students') is not None: range_params['gte'] = filters['min_students']
            if filters.get('max_students') is not None: range_params['lte'] = filters['max_students']
            conditions.append(FieldCondition(key="metadata.total_students", range=Range(**range_params)))
            
        if filters.get('min_teachers') is not None or filters.get('max_teachers') is not None:
            range_params = {}
            if filters.get('min_teachers') is not None: range_params['gte'] = filters['min_teachers']
            if filters.get('max_teachers') is not None: range_params['lte'] = filters['max_teachers']
            conditions.append(FieldCondition(key="metadata.total_teachers", range=Range(**range_params)))

        query_filter = Filter(must=conditions) if conditions else None
        
        try:
            # 1. Get Total Count (for user info)
            count_result = self.client.count(
                collection_name=self.collection,
                count_filter=query_filter
            )
            total_count = count_result.count
            
            # 2. Get Page Data
            response = self.client.scroll(
                collection_name=self.collection,
                scroll_filter=query_filter,
                limit=limit,
                offset=offset,
                with_payload=True
            )
            points, next_offset = response
            
            return points, total_count, next_offset
            
        except Exception as e:
            logger.error(f"Search by criteria error: {e}")
            return [], 0, None
            
    def search_teachers(self, filters: Dict[str, Any]) -> List[Dict]:
        """
        Search specific teacher/personnel types in edu_teachers_v5
        """
        conditions = []
        
        # 1. School Name (Exact or Fuzzy?)
        # For now, if school_name is provided, we try exact match on metadata
        if filters.get('school_name'):
             conditions.append(FieldCondition(key="metadata.school_name", match=MatchValue(value=filters['school_name'])))
             
        # 2. Location
        if filters.get('province'):
            conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=filters['province'])))
            
        # 3. Personnel Type (The main goal)
        if filters.get('person_type'):
             conditions.append(FieldCondition(key="metadata.person_type", match=MatchValue(value=filters['person_type'])))
             
        query_filter = Filter(must=conditions) if conditions else None
        
        try:
            # We want to aggregate counts, but for now let's just return the raw rows
            # The responder will sum them up.
            response = self.client.scroll(
                collection_name=COLLECTIONS["teachers"], # edu_teachers_v5
                scroll_filter=query_filter,
                limit=100, # Should be enough for a school's breakdown
                with_payload=True
            )
            
            return [p.payload for p in response[0]]
            
        except Exception as e:
            logger.error(f"Search teachers error: {e}")
            return []

    def search_by_subdistrict(self, province: str, subdistrict: str, district: str = None, agency: str = None, limit: int = 20) -> List:
        """List schools in a subdistrict with robust name matching"""
        
        base_subdistrict = subdistrict.replace('ตำบล', '').replace('ต.', '').replace('แขวง', '').strip()
        
        subdistrict_variants = {
            base_subdistrict,
            f"ตำบล{base_subdistrict}",
            f"ต.{base_subdistrict}",
            f"แขวง{base_subdistrict}",
        }
            
        logger.info(f"🔎 Searching subdistrict variations for '{subdistrict}': {list(subdistrict_variants)}")

        subdistrict_should = [
            FieldCondition(key="metadata.subdistrict", match=MatchValue(value=d))
            for d in subdistrict_variants
        ]
        
        conditions = [
            Filter(should=subdistrict_should)
        ]
        
        if province:
             conditions.insert(0, FieldCondition(key="metadata.province", match=MatchValue(value=province)))
        
        if district:
             conditions.append(FieldCondition(key="metadata.district", match=MatchValue(value=district)))
             
        if agency:
            conditions.insert(0, FieldCondition(key="metadata.agency", match=MatchValue(value=agency)))
        
        try:
            response = self.client.scroll(
                collection_name=self.collection,
                scroll_filter=Filter(must=conditions),
                limit=limit * 5,
                with_payload=True
            )
            
            seen_keys = set()
            unique_results = []
            for point in response[0]:
                meta = point.payload.get('metadata', {})
                code = meta.get('school_id')
                name = meta.get('school_name', '')
                # Fallback key
                key = code if code else f"{name}_{meta.get('province','')}"
                
                if key and key not in seen_keys:
                    seen_keys.add(key)
                    unique_results.append(point)
                    if len(unique_results) >= limit:
                        break
            
            return unique_results
        except Exception as e:
            logger.error(f"School search by subdistrict error: {e}")
            return []
    
    def get_school_details(self, school_name: str) -> Optional[Dict]:
        """Get detailed information about a specific school"""
        clean_name = school_name.strip()
        for prefix in ['โรงเรียน', 'ร.ร.', 'รร.', 'รร']:
            if clean_name.startswith(prefix):
                clean_name = clean_name[len(prefix):].strip()
        
        logger.info(f"🔍 Searching for school: '{school_name}' → '{clean_name}'")
        
        results = self.search_by_name(clean_name, limit=10)
        if results:
            for res in results:
                meta = res.payload.get('metadata', {})
                db_school_name = meta.get('school_name', '').lower()
                query_name = school_name.lower()
                if query_name in db_school_name or db_school_name in query_name:
                    logger.info(f"🏫 Found school: {meta.get('school_name')}")
                    return meta
            top_result = results[0]
            if hasattr(top_result, 'score') and top_result.score > 0.7:
                logger.info(f"🏫 Best match: {results[0].payload.get('metadata', {}).get('school_name')}")
                return results[0].payload.get('metadata', {})
        return None
    
    def count_schools(self, province: str = None, district: str = None, agency: str = None) -> int:
        """Count unique schools with optional filters"""
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
            scroll_filter = Filter(must=conditions) if conditions else None
            unique_codes = set()
            offset = None
            
            while True:
                response = self.client.scroll(
                    collection_name=self.collection,
                    scroll_filter=scroll_filter,
                    limit=1000,
                    offset=offset,
                    with_payload=["metadata.school_id"]
                )
                points, next_offset = response
                
                if not points:
                    break
                    
                for point in points:
                    meta = point.payload.get('metadata', {})
                    code = meta.get('school_id')
                    name = meta.get('school_name', '')
                    # Fallback key
                    key = code if code else f"{name}_{meta.get('province','')}"
                    
                    if key:
                        unique_codes.add(key)
                
                if next_offset is None:
                    break
                offset = next_offset
            
            logger.info(f"🏫 Unique schools count: {len(unique_codes)}")
            return len(unique_codes)
        except Exception as e:
            logger.error(f"School count error: {e}")
            return 0

    def get_student_statistics(self, school_id: str) -> Dict[str, Any]:
        """
        Fetch detailed student statistics from specific collection (v5).
        Aggregates by grade and gender.
        """
        if not school_id:
            return {}

        try:
            # Assumed collection name
            collection_name = "edu_students_v5" 
            
            # Fetch all records for this school
            response = self.client.scroll(
                collection_name=collection_name,
                scroll_filter=Filter(must=[
                    FieldCondition(key="metadata.school_id", match=MatchValue(value=str(school_id)))
                ]),
                limit=100,
                with_payload=True
            )
            
            records = response[0]
            if not records:
                return {}
                
            stats = {
                "total_students": 0,
                "by_grade": {},
                "source": collection_name
            }
            
            for point in records:
                meta = point.payload.get('metadata', {})
                
                # Extract fields based on investigation
                raw_grade = meta.get('grade', 'ไม่ระบุ')
                count = int(meta.get('count', 0))
                gender = meta.get('gender', 'ไม่ระบุ')
                
                # Simplify grade name (e.g. "มัธยมศึกษาปีที่ 3 /เกรด 9/..." -> "มัธยมศึกษาปีที่ 3")
                grade_parts = raw_grade.split('/')
                grade_name = grade_parts[0].strip()
                
                # Further normalize common patterns if needed
                if "ประถมศึกษา" in grade_name:
                    grade_name = grade_name.replace("ประถมศึกษาปีที่", "ป.")
                elif "มัธยมศึกษา" in grade_name:
                   grade_name = grade_name.replace("มัธยมศึกษาปีที่", "ม.")
                elif "อนุบาล" in grade_name:
                   grade_name = grade_name.replace("อนุบาลปีที่", "อ.")
                
                # Initialize grade entry if not exists
                if grade_name not in stats["by_grade"]:
                    stats["by_grade"][grade_name] = {"total": 0, "male": 0, "female": 0}
                    
                # Aggregation
                stats["by_grade"][grade_name]["total"] += count
                stats["total_students"] += count
                
                if gender == "ชาย":
                    stats["by_grade"][grade_name]["male"] += count
                elif gender == "หญิง":
                    stats["by_grade"][grade_name]["female"] += count
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Error fetching student statistics: {e}")
            return {}
