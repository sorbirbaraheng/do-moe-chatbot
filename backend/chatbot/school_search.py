"""
School Search Engine for Education Chatbot
Handles school-specific searches by name, province, district
"""

import logging
from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher

import google.generativeai as genai
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from .constants import COLLECTIONS

logger = logging.getLogger(__name__)


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
        
        # 1. Try text-match filter first
        try:
            response = self.client.scroll(
                collection_name=self.collection,
                scroll_filter=Filter(must=[
                    FieldCondition(key="metadata.school_name", match=MatchValue(value=name))
                ]),
                limit=limit * 5,
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
