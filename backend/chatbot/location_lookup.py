"""
Location Lookup Service
Provides province/district/subdistrict name normalization using database lookup + fuzzy matching.
Eliminates need for hardcoded keyword lists.
"""

import logging
from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher
import time


from qdrant_client import QdrantClient
from .constants import COLLECTION_NAMES

logger = logging.getLogger(__name__)


class LocationLookup:
    """
    Lookup service for normalizing location names against database.
    Uses fuzzy matching to handle typos and short names.
    """
    
    # Cache settings
    CACHE_TTL_SECONDS = 3600  # 1 hour
    
    # Common province aliases (semantic mappings that fuzzy match can't easily catch)
    PROVINCE_SEMANTIC_ALIASES = {
        'กทม': 'กรุงเทพมหานคร',
        'กทม.': 'กรุงเทพมหานคร',
        'กรุงเทพ': 'กรุงเทพมหานคร',
        'กรุงเทพฯ': 'กรุงเทพมหานคร',
        'โคราช': 'นครราชสีมา',
        'อีสาน': None,  # Region, not province
        'เหนือ': None,
        'ใต้': None,
    }
    
    def __init__(self, client: QdrantClient):
        self.client = client
        self._provinces_cache: List[str] = []
        self._districts_cache: Dict[str, List[str]] = {}  # province -> districts
        self._cache_timestamp: float = 0
        
    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid"""
        return (time.time() - self._cache_timestamp) < self.CACHE_TTL_SECONDS and len(self._provinces_cache) > 0
    
    def _load_provinces_from_db(self) -> List[str]:
        """Load unique province names from database"""
        try:
            # Scroll through education_schools to get unique provinces
            provinces = set()
            offset = None
            
            for _ in range(50):  # Max 50 iterations to avoid infinite loop
                response = self.client.scroll(
                    collection_name=COLLECTION_NAMES["schools"],
                    limit=1000,
                    offset=offset,
                    with_payload=["metadata.province"]
                )
                points, next_offset = response
                
                if not points:
                    break
                    
                for point in points:
                    province = point.payload.get('metadata', {}).get('province')
                    if province:
                        provinces.add(province)
                
                if next_offset is None or len(provinces) > 77:  # Thailand has 77 provinces
                    break
                offset = next_offset
            
            logger.info(f"📍 Loaded {len(provinces)} unique provinces from database")
            return sorted(list(provinces))
            
        except Exception as e:
            logger.error(f"Failed to load provinces: {e}")
            return []
    
    def get_all_provinces(self) -> List[str]:
        """Get all province names from database (cached)"""
        if not self._is_cache_valid():
            self._provinces_cache = self._load_provinces_from_db()
            self._cache_timestamp = time.time()
        return self._provinces_cache
    
    def _fuzzy_match(self, query: str, candidates: List[str], threshold: float = 0.6) -> Optional[Tuple[str, float]]:
        """
        Find best fuzzy match for query in candidates.
        Returns (matched_name, score) or None if no match above threshold.
        """
        if not query or not candidates:
            return None
            
        query_lower = query.lower().strip()
        best_match = None
        best_score = 0
        
        for candidate in candidates:
            candidate_lower = candidate.lower()
            
            # Exact match
            if query_lower == candidate_lower:
                return (candidate, 1.0)
            
            # Substring match (high priority)
            if query_lower in candidate_lower or candidate_lower in query_lower:
                score = 0.9
                if score > best_score:
                    best_score = score
                    best_match = candidate
                continue
            
            # Fuzzy match using SequenceMatcher
            ratio = SequenceMatcher(None, query_lower, candidate_lower).ratio()
            if ratio > best_score and ratio >= threshold:
                best_score = ratio
                best_match = candidate
        
        if best_match:
            return (best_match, best_score)
        return None
    
    def normalize_province(self, name: str) -> Optional[str]:
        """
        Normalize province name to match database format.
        
        Examples:
            - "กรุงเทพ" → "กรุงเทพมหานคร"
            - "กทม" → "กรุงเทพมหานคร"
            - "โคราช" → "นครราชสีมา"
            - "เชียงไหม่" (typo) → "เชียงใหม่"
        """
        if not name:
            return None
            
        name = name.strip()
        
        # Check semantic aliases first (for abbreviations that fuzzy can't catch)
        if name in self.PROVINCE_SEMANTIC_ALIASES:
            return self.PROVINCE_SEMANTIC_ALIASES[name]
        
        # Get provinces from database
        provinces = self.get_all_provinces()
        
        # Try fuzzy matching
        match_result = self._fuzzy_match(name, provinces, threshold=0.6)
        
        if match_result:
            matched_name, score = match_result
            logger.info(f"📍 Province normalized: '{name}' → '{matched_name}' (score: {score:.2f})")
            return matched_name
        
        logger.warning(f"⚠️ Could not normalize province: '{name}'")
        return None
    
    def normalize_district(self, name: str, province: str = None) -> Optional[str]:
        """
        Normalize district name to match database format.
        If province is provided, search only within that province.
        """
        if not name:
            return None
            
        name = name.strip()
        
        # Remove common prefixes
        for prefix in ['อำเภอ', 'เขต', 'อ.']:
            if name.startswith(prefix):
                name = name[len(prefix):].strip()
        
        # Special handling for "เมือง" district - append province name
        # e.g. "เมือง" + "ปัตตานี" -> "เมืองปัตตานี"
        if name == "เมือง" and province:
            name = f"เมือง{province}"
            logger.info(f"📍 District expanded: 'เมือง' → '{name}'")
        
        try:
            # Build filter for province if provided
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            
            scroll_filter = None
            if province:
                scroll_filter = Filter(must=[
                    FieldCondition(key="metadata.province", match=MatchValue(value=province))
                ])
            
            # Get unique districts
            districts = set()
            response = self.client.scroll(
                collection_name=COLLECTION_NAMES["schools"],
                scroll_filter=scroll_filter,
                limit=500,
                with_payload=["metadata.district"]
            )
            
            for point in response[0]:
                district = point.payload.get('metadata', {}).get('district')
                if district:
                    districts.add(district)
            
            # Fuzzy match
            match_result = self._fuzzy_match(name, list(districts), threshold=0.6)
            
            if match_result:
                matched_name, score = match_result
                logger.info(f"📍 District normalized: '{name}' → '{matched_name}' (score: {score:.2f})")
                return matched_name
                
        except Exception as e:
            logger.error(f"District normalization error: {e}")
        
        return None
    
    def normalize_subdistrict(self, name: str, province: str = None, district: str = None) -> Optional[str]:
        """
        Normalize subdistrict name to match database format.
        """
        if not name:
            return None
        
        # Skip national/region keywords - don't try to match these to subdistricts
        skip_keywords = [
            'ประเทศไทย', 'ประเทศ', 'ทั่วประเทศ', 'ทั้งประเทศ', 'ทั้งหมด', 'ไทย',
            'ภาคเหนือ', 'ภาคใต้', 'ภาคกลาง', 'ภาคอีสาน', 'ภาคตะวันออก', 'ภาคตะวันตก',
            'ภาคตะวันออกเฉียงเหนือ', 'อีสาน', 'เหนือ', 'ใต้', 'กลาง'
        ]
        if any(kw in name for kw in skip_keywords):
            return None
            
        name = name.strip()
        
        # Remove common prefixes
        for prefix in ['ตำบล', 'แขวง', 'ต.']:
            if name.startswith(prefix):
                name = name[len(prefix):].strip()
        
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            
            conditions = []
            if province:
                conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=province)))
            if district:
                conditions.append(FieldCondition(key="metadata.district", match=MatchValue(value=district)))
            
            scroll_filter = Filter(must=conditions) if conditions else None
            
            # Get unique subdistricts
            subdistricts = set()
            response = self.client.scroll(
                collection_name=COLLECTION_NAMES["schools"],
                scroll_filter=scroll_filter,
                limit=500,
                with_payload=["metadata.subdistrict"]
            )
            
            for point in response[0]:
                subdistrict = point.payload.get('metadata', {}).get('subdistrict')
                if subdistrict:
                    subdistricts.add(subdistrict)
            
            # Fuzzy match
            match_result = self._fuzzy_match(name, list(subdistricts), threshold=0.6)
            
            if match_result:
                matched_name, score = match_result
                logger.info(f"📍 Subdistrict normalized: '{name}' → '{matched_name}' (score: {score:.2f})")
                return matched_name
                
        except Exception as e:
            logger.error(f"Subdistrict normalization error: {e}")
        
        return None


# Singleton instance
_location_lookup_instance: Optional[LocationLookup] = None


def get_location_lookup(client: QdrantClient) -> LocationLookup:
    """Get or create LocationLookup singleton"""
    global _location_lookup_instance
    if _location_lookup_instance is None:
        _location_lookup_instance = LocationLookup(client)
    return _location_lookup_instance
