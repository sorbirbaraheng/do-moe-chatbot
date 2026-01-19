"""
Search Engine for Education Chatbot
Handles vector search, metadata filtering, and query expansion
"""

import time
import logging
from typing import List, Optional

import google.generativeai as genai
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from .types import ParsedQuery, QueryLevel
from .constants import REGIONS

logger = logging.getLogger(__name__)


class SearchEngine:
    """Production-ready search engine with fallback strategies"""
    
    def __init__(self, client: QdrantClient, parser=None):
        self.client = client
        self.parser = parser
    
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
                
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = f"แปลงคำค้นหานี้ให้เป็นประโยคที่ใช้ค้นหาใน Vector Database ภาษาไทย: '{query}' (ขอแค่ประโยคผลลัพธ์ ไม่ต้องอธิบาย)"
            
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
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=query,
                task_type="retrieval_query"
            )
            query_vector = result['embedding']
            
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
