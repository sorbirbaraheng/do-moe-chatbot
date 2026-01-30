
"""
Search Engine for Education Chatbot
Handles vector search, metadata filtering, query expansion, and smart collection routing
"""

import time
import logging
from typing import List, Optional, Tuple

import google.generativeai as genai
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from .types import ParsedQuery, QueryLevel
from .constants import REGIONS, COLLECTION_KEYWORDS, COLLECTION_SEARCH_ORDER, PRIMARY_COLLECTION

logger = logging.getLogger(__name__)


def route_to_collection(query: str) -> Tuple[str, float]:
    """
    Smart Collection Routing - เลือก Collection ที่เหมาะสมตาม Query
    Returns: (collection_name, confidence_score)
    """
    query_lower = query.lower()
    scores = {}
    
    for collection, keywords in COLLECTION_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            if keyword.lower() in query_lower:
                # Higher weight for longer/more specific keywords
                score += len(keyword)
        scores[collection] = score
    
    if scores:
        best_collection = max(scores, key=scores.get)
        best_score = scores[best_collection]
        
        if best_score > 0:
            # Normalize confidence (0-1)
            confidence = min(1.0, best_score / 20.0)
            logger.info(f"🎯 Smart Routing: '{query[:30]}...' → {best_collection} (confidence: {confidence:.2f})")
            return best_collection, confidence
    
    # Fallback to primary
    logger.info(f"🔄 Fallback routing → {PRIMARY_COLLECTION}")
    return PRIMARY_COLLECTION, 0.5


class SearchEngine:
    """Production-ready search engine with fallback strategies"""
    

    def __init__(self, client: QdrantClient, parser=None, llm_provider=None):
        self.client = client
        self.parser = parser
        self.llm_provider = llm_provider
    
    def search(self, parsed_query: ParsedQuery, collection_name: str, top_k: int = 50) -> List:
        """
        Smart Search (World Class RAG):
        1. Contextual Filters (Metadata)
        2. Query Expansion (Gemini)
        3. Filtered Vector Search (Hybrid)
        """
        start_time = time.time()
        results = []
        
        try:
            # 1. Build Metadata Filters
            conditions = []
            if parsed_query.province:
                conditions.append(FieldCondition(key="metadata.province", match=MatchValue(value=parsed_query.province)))
            if parsed_query.district:
                conditions.append(FieldCondition(key="metadata.district", match=MatchValue(value=parsed_query.district)))
            if parsed_query.subdistrict:
                conditions.append(FieldCondition(key="metadata.subdistrict", match=MatchValue(value=parsed_query.subdistrict)))
            if parsed_query.agency:
                conditions.append(FieldCondition(key="metadata.agency", match=MatchValue(value=parsed_query.agency)))
            
            qdrant_filter = Filter(must=conditions) if conditions else None
            
            # 2. Query Expansion
            expanded_query = self._expand_query(parsed_query.original_query)
            
            # 3. Hybrid Search
            results = self._semantic_search(expanded_query, collection_name, top_k, qdrant_filter)
            logger.info(f"🧠 Smart Search: '{expanded_query}' + Filters={len(conditions)} -> {len(results)} hits")
            
            # 4. Fallback
            if not results:
                logger.info("⚠️ Vector search failed, falling back to pure metadata filter")
                response = self.client.scroll(
                    collection_name=collection_name,
                    scroll_filter=qdrant_filter,
                    limit=top_k,
                    with_payload=True
                )
                results = response[0]

        except Exception as e:
            logger.error(f"Search error: {e}")
        
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"Search completed in {elapsed:.2f}ms")
        return results

    def _expand_query(self, query: str) -> str:
        """Expand query using Gemini to improve recall"""
        try:
            if len(query) < 5: 
                return query
                
            prompt = f"แปลงคำค้นหานี้ให้เป็นประโยคที่ใช้ค้นหาใน Vector Database ภาษาไทย: '{query}' (ขอแค่ประโยคผลลัพธ์ ไม่ต้องอธิบาย)"
            
            if self.llm_provider:
                response = self.llm_provider.generate_content(prompt)
                expanded = response.text.strip()
            else:
                # Legacy fallback
                model = genai.GenerativeModel("gemini-1.5-flash")
                response = model.generate_content(prompt, generation_config={"max_output_tokens": 50})
                expanded = response.text.strip()
            
            if len(expanded) > 200:
                return query
                
            return expanded
        except Exception as e:
            logger.warning(f"Query expansion failed: {e}")
            return query
    
    def _semantic_search(self, query: str, collection_name: str, top_k: int, filters: Filter = None) -> List:
        """Semantic search using embeddings with filters"""
        try:
            if self.llm_provider:
                query_vector = self.llm_provider.embed_content(query)
            else:
                # Legacy fallback
                result = genai.embed_content(
                    model="models/text-embedding-004",
                    content=query,
                    task_type="retrieval_query"
                )
                query_vector = result['embedding']
            
            if not query_vector:
                logger.warning("Generated empty embedding vector")
                return []

            # Use new query_points API (qdrant-client >= 1.7.0)
            response = self.client.query_points(
                collection_name=collection_name,
                query=query_vector,
                query_filter=filters,
                limit=top_k,
                with_payload=True
            )
            return response.points
            
        except Exception as e:
            logger.error(f"Semantic search error: {e}")
            return []
    
    def ranking_search(self, parsed_query: ParsedQuery, collection_name: str, top_k: int = 1000) -> List:
        """
        Special search for ranking queries - fetches ALL data or filtered by region/province
        Then aggregates and sorts by total count
        """
        logger.info(f"🏆 Ranking search: region={parsed_query.region}, province={parsed_query.province}")
        
        conditions = []
        
        if parsed_query.province:
            conditions.append(
                FieldCondition(key="metadata.province", match=MatchValue(value=parsed_query.province))
            )
            logger.info(f"   Filter by province: {parsed_query.province}")

        if parsed_query.agency:
            conditions.append(
                FieldCondition(key="metadata.agency", match=MatchValue(value=parsed_query.agency))
            )
            logger.info(f"   Filter by agency: {parsed_query.agency}")
        
        elif parsed_query.region:
            region_provinces = REGIONS.get(parsed_query.region, [])
            if region_provinces:
                logger.info(f"   Filter by region: {parsed_query.region} ({len(region_provinces)} provinces)")
        
        try:
            if conditions:
                response = self.client.scroll(
                    collection_name=collection_name,
                    scroll_filter=Filter(must=conditions),
                    limit=top_k,
                    with_payload=True
                )
            else:
                response = self.client.scroll(
                    collection_name=collection_name,
                    limit=top_k,
                    with_payload=True
                )
            
            results = response[0]
            
            # Filter by region (client-side)
            if parsed_query.region and not parsed_query.province:
                region_provinces = REGIONS.get(parsed_query.region, [])
                if region_provinces:
                    filtered = []
                    for r in results:
                        meta = r.payload.get('metadata', {})
                        if meta.get('province') in region_provinces:
                            filtered.append(r)
                    results = filtered
                    logger.info(f"   After region filter: {len(results)} results")
            
            logger.info(f"   Ranking search found: {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Ranking search error: {e}")
            return []

    def smart_search(self, query: str, parsed_query: ParsedQuery, top_k: int = 50) -> dict:
        """
        Smart Multi-Collection Search
        1. Route to best collection based on query
        2. Search in that collection
        3. Fallback to secondary collections if needed
        
        Returns: {
            "results": [...],
            "collection": "collection_name",
            "confidence": 0.0-1.0
        }
        """
        start_time = time.time()
        
        # 1. Smart routing
        best_collection, confidence = route_to_collection(query)
        
        # 2. Search in best collection
        results = self.search(parsed_query, best_collection, top_k)
        
        # 3. Fallback if no results
        if not results and confidence < 0.8:
            logger.info(f"⚠️ No results in {best_collection}, trying fallback collections...")
            for fallback in COLLECTION_SEARCH_ORDER:
                if fallback != best_collection:
                    try:
                        results = self.search(parsed_query, fallback, top_k)
                        if results:
                            logger.info(f"✅ Found {len(results)} results in fallback: {fallback}")
                            best_collection = fallback
                            break
                    except Exception as e:
                        logger.warning(f"Fallback search in {fallback} failed: {e}")
                        continue
        
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"🔍 Smart search completed in {elapsed:.2f}ms | Collection: {best_collection} | Results: {len(results)}")
        
        return {
            "results": results,
            "collection": best_collection,
            "confidence": confidence
        }

    def multi_collection_search(self, query: str, parsed_query: ParsedQuery, top_k: int = 50) -> dict:
        """
        🔥 Multi-Collection Search - Search ALL relevant collections automatically
        
        Based on query keywords, determines which collections to search and aggregates results.
        This provides comprehensive answers by pulling data from multiple sources.
        
        Returns: {
            "results": [...],
            "collections_searched": ["col1", "col2"],
            "results_by_collection": {"col1": [...], "col2": [...]},
            "primary_collection": "col1"
        }
        """
        start_time = time.time()
        query_lower = query.lower()
        
        # Determine which collections to search based on keywords
        collections_to_search = []
        
        for collection, keywords in COLLECTION_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in query_lower:
                    if collection not in collections_to_search:
                        collections_to_search.append(collection)
                        logger.info(f"🎯 Matched keyword '{keyword}' → {collection}")
                    break
        
        # If no specific keywords found, use default search order
        if not collections_to_search:
            collections_to_search = COLLECTION_SEARCH_ORDER[:2]
            logger.info(f"🔄 No keywords matched, using defaults: {collections_to_search}")
        
        # Search each relevant collection
        all_results = []
        results_by_collection = {}
        primary_collection = None
        
        for collection in collections_to_search:
            try:
                collection_results = self.search(parsed_query, collection, top_k)
                if collection_results:
                    results_by_collection[collection] = collection_results
                    all_results.extend(collection_results)
                    if not primary_collection:
                        primary_collection = collection
                    logger.info(f"✅ {collection}: {len(collection_results)} results")
                else:
                    logger.info(f"⚪ {collection}: 0 results")
            except Exception as e:
                logger.warning(f"❌ Error searching {collection}: {e}")
                continue
        
        # Additional: Search for grade+gender specific queries in edu_students_v5
        grade_keywords = ['ม.1', 'ม.2', 'ม.3', 'ม.4', 'ม.5', 'ม.6', 'ป.1', 'ป.2', 'ป.3', 'ป.4', 'ป.5', 'ป.6',
                         'มัธยมศึกษาปีที่', 'ประถมศึกษาปีที่', 'อนุบาล', 'ระดับชั้น']
        gender_keywords = ['เพศชาย', 'เพศหญิง', 'ชาย', 'หญิง', 'นักเรียนชาย', 'นักเรียนหญิง']
        
        has_grade = any(kw in query_lower for kw in grade_keywords)
        has_gender = any(kw in query_lower for kw in gender_keywords)
        
        if (has_grade or has_gender) and 'edu_students_v5' not in collections_to_search:
            logger.info(f"🎓 Grade/Gender detected - adding edu_students_v5 search")
            try:
                student_results = self.search(parsed_query, 'edu_students_v5', top_k)
                if student_results:
                    results_by_collection['edu_students_v5'] = student_results
                    all_results.extend(student_results)
                    if not primary_collection:
                        primary_collection = 'edu_students_v5'
                    logger.info(f"✅ edu_students_v5: {len(student_results)} results")
            except Exception as e:
                logger.warning(f"❌ Error searching edu_students_v5: {e}")
        
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"🔍 Multi-collection search completed in {elapsed:.2f}ms | Collections: {list(results_by_collection.keys())} | Total: {len(all_results)}")
        
        return {
            "results": all_results,
            "collections_searched": list(results_by_collection.keys()),
            "results_by_collection": results_by_collection,
            "primary_collection": primary_collection or PRIMARY_COLLECTION
        }
