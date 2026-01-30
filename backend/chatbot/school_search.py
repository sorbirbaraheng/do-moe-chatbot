"""
School Search Engine for Education Chatbot
Handles school-specific searches by name, province, district
"""

import logging
from typing import List, Dict, Optional, Tuple, Any
from difflib import SequenceMatcher

import google.generativeai as genai
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

from .constants import COLLECTIONS, PRIMARY_COLLECTION

logger = logging.getLogger(__name__)


class SchoolSearchEngine:
    """Search engine for education data collection"""
    
    def __init__(self, client: QdrantClient):
        self.client = client
        # Use unified collection (thailand_education) for all queries
        self.collection = PRIMARY_COLLECTION
    
    def _normalize_name(self, name: str) -> str:
        """Normalize school name for consistent matching
        - Remove spaces
        - Remove common prefixes
        - Convert Thai numerals
        """
        if not name:
            return ""
            
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
        """Search schools by name - try text match first, then semantic search (deduplicated by school_code)"""
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
        
        # 1. Try text-match filter first
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
                    # Note: This checks strictly school_name. 
                    # Ideally we want a specialized field like 'normalized_name' in DB.
                    # But often names in DB are mixed "รร.บ้าน..." or "โรงเรียนบ้าน..."
                    # So we try scanning common variations logic OR just relying on cleaned string 
                    # implicitly if semantic search handles it (but semantic search failed here).
                    # 
                    # Hack: Since we can't easily query "normalized" against raw field efficiently without new index,
                    # We will rely on Semantic Search to pick up the slack, BUT we can try 
                    # matching against "รร.{norm_name}" or "{norm_name}" if stored without prefix.
                    
                    # Try fuzzy match manually? No, strict match on key variations?
                    # Let's try matching 'start' using LIKE? Qdrant support match text?
                    # Since we identified the issue is "รร.เทศบาล4..." vs "โรงเรียนเทศบาล 4...",
                    # Normalized 'เทศบาล4...' should match if we could partial match.
                    
                    # Instead of complex logic, let's just use the NORMALIZED string for the SEMANTIC SEARCH too.
                    # But first, let's pass the normalized name to semantic search if direct match fails.
                    pass 
            
            if results:
                logger.info(f"🏫 Text match found {len(results)} unique schools for '{name}'")
                return results
        except Exception as e:
            logger.warning(f"Text match failed: {e}")
        
        # 2. Fallback to semantic search
        try:
            # Use normalized name for semantic search to reduce noise
            search_query = f"โรงเรียน{self._normalize_name(name)}"
            
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=search_query,
                task_type="retrieval_query"
            )
            query_vector = result['embedding']
            
            # Use new query_points API (qdrant-client >= 1.7.0)
            response = self.client.query_points(
                collection_name=self.collection,
                query=query_vector,
                limit=limit * 5,
                with_payload=True
            )
            results = response.points
            unique_results = deduplicate(results, limit)
            logger.info(f"🔍 Semantic search found {len(unique_results)} unique schools for '{name}'")
            return unique_results
        except Exception as e:
            logger.error(f"School search by name error: {e}")
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
