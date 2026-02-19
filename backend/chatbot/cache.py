"""
Caching System for Education Chatbot
- SemanticCache: Qdrant-based similarity matching
- HybridCache: Redis L1 + Semantic L2
"""

import os
import time
import logging
import hashlib
from typing import Optional

logger = logging.getLogger(__name__)



class SemanticCache:
    """Semantic Caching using Qdrant for instant replies"""
    
    def __init__(self, client, llm_provider=None, collection_name: str = "semantic_cache"):
        from qdrant_client.models import VectorParams, Distance, PointStruct
        
        self.client = client
        self.llm_provider = llm_provider
        self.collection_name = collection_name
        self.vector_size = 768  # models/text-embedding-004
        self.threshold = 0.97
        self.VectorParams = VectorParams
        self.Distance = Distance
        self.PointStruct = PointStruct
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Create collection if not exists"""
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            if not exists:
                logger.info(f"🆕 Creating semantic cache collection: {self.collection_name}")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=self.VectorParams(size=self.vector_size, distance=self.Distance.COSINE)
                )
        except Exception as e:
            logger.error(f"Error initializing semantic cache: {e}")

    def check(self, query: str, context: dict = None) -> Optional[str]:
        """Check cache for similar queries within the same context"""
        try:
            vector = []
            if self.llm_provider:
                vector = self.llm_provider.embed_content(query)
            else:
                 import google.generativeai as genai
                 result = genai.embed_content(
                     model="models/text-embedding-004",
                     content=query,
                     task_type="retrieval_query"
                 )
                 vector = result['embedding']
            
            if not vector:
                return None
            
            # Build context filter for Qdrant
            query_filter = None
            if context:
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                conditions = []
                ctx_province = context.get("province") or "__none__"
                ctx_year = context.get("year") or "__none__"
                conditions.append(FieldCondition(key="ctx_province", match=MatchValue(value=ctx_province)))
                conditions.append(FieldCondition(key="ctx_year", match=MatchValue(value=ctx_year)))
                query_filter = Filter(must=conditions)
            
            # Use new query_points API (qdrant-client >= 1.7.0)
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=vector,
                query_filter=query_filter,
                limit=1
            )
            hits = response.points
            
            if hits and hits[0].score >= self.threshold:
                logger.info(f"⚡ Cache Hit! Score: {hits[0].score:.4f} (ctx: {context})")
                return hits[0].payload.get("response")
                
        except Exception as e:
            logger.warning(f"Cache check failed: {e}")
        return None

    def save(self, query: str, response: str, context: dict = None):
        """Save response to cache with context metadata"""
        try:
            import uuid
            
            vector = []
            if self.llm_provider:
                vector = self.llm_provider.embed_content(query)
            else:
                import google.generativeai as genai
                result = genai.embed_content(
                    model="models/text-embedding-004",
                    content=query,
                    task_type="retrieval_query"
                )
                vector = result['embedding']
            
            if not vector:
                return

            payload = {"query": query, "response": response, "timestamp": time.time()}
            # Store context in payload for filtering
            if context:
                payload["ctx_province"] = context.get("province") or "__none__"
                payload["ctx_year"] = context.get("year") or "__none__"
            else:
                payload["ctx_province"] = "__none__"
                payload["ctx_year"] = "__none__"

            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    self.PointStruct(
                        id=str(uuid.uuid4()),
                        vector=vector,
                        payload=payload
                    )
                ]
            )
        except Exception as e:
            logger.warning(f"Cache save failed: {e}")


class HybridCache:
    """
    Two-layer cache for production:
    - L1: Redis (fast exact match, ~1ms)
    - L2: SemanticCache (similar query match, ~500ms)
    """
    
    def __init__(self, qdrant_client, llm_provider=None):
        self.semantic_cache = SemanticCache(qdrant_client, llm_provider=llm_provider)
        self.redis_client = None
        self.ttl = int(os.getenv('REDIS_CACHE_TTL', 3600))  # 1 hour default
        
        # Try to connect to Redis
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis connection with graceful fallback"""
        try:
            import redis
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            # Test connection
            self.redis_client.ping()
            logger.info(f"✅ Redis connected: {redis_url}")
        except Exception as e:
            logger.warning(f"⚠️ Redis unavailable, using Semantic cache only: {e}")
            self.redis_client = None
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query for consistent hashing"""
        return query.lower().strip()
    
    def _get_cache_key(self, query: str, context: dict = None) -> str:
        """Generate context-aware Redis key from query + province/year"""
        normalized = self._normalize_query(query)
        ctx_suffix = ""
        if context:
            p = context.get("province") or "none"
            y = context.get("year") or "none"
            ctx_suffix = f":{p}:{y}"
        hash_val = hashlib.md5((normalized + ctx_suffix).encode()).hexdigest()[:16]
        return f"domoe:cache:{hash_val}"
    
    def check(self, query: str, context: dict = None) -> Optional[str]:
        """Check cache: Redis first, then Semantic (context-aware)"""
        # L1: Try Redis (fast exact match, scoped by context)
        if self.redis_client:
            try:
                cache_key = self._get_cache_key(query, context)
                cached = self.redis_client.get(cache_key)
                if cached:
                    logger.info(f"⚡ Redis L1 Cache Hit! (ctx: {context})")
                    return cached
            except Exception as e:
                logger.warning(f"Redis check failed: {e}")
        
        # L2: Try Semantic Cache (filtered by context)
        return self.semantic_cache.check(query, context)
    
    def save(self, query: str, response: str, context: dict = None):
        """Save to both caches (context-aware)"""
        # Save to Redis (L1) with context-scoped key
        if self.redis_client:
            try:
                cache_key = self._get_cache_key(query, context)
                self.redis_client.setex(cache_key, self.ttl, response)
            except Exception as e:
                logger.warning(f"Redis save failed: {e}")
        
        # Save to Semantic Cache (L2) with context metadata
        self.semantic_cache.save(query, response, context)

    def flush(self) -> dict:
        """Flush all caches (Redis L1 + Qdrant semantic cache)"""
        result = {"redis_deleted": 0, "semantic_deleted": 0}
        
        # Flush Redis L1
        if self.redis_client:
            try:
                keys = self.redis_client.keys("domoe:cache:*")
                if keys:
                    result["redis_deleted"] = self.redis_client.delete(*keys)
                logger.info(f"🗑️ Redis cache flushed: {result['redis_deleted']} keys")
            except Exception as e:
                logger.warning(f"Redis flush failed: {e}")
        
        # Flush Qdrant semantic cache
        try:
            from qdrant_client.models import FilterSelector, Filter
            info = self.semantic_cache.client.get_collection(self.semantic_cache.collection_name)
            result["semantic_deleted"] = info.points_count or 0
            if result["semantic_deleted"] > 0:
                self.semantic_cache.client.delete(
                    self.semantic_cache.collection_name,
                    points_selector=FilterSelector(filter=Filter())
                )
            logger.info(f"🗑️ Semantic cache flushed: {result['semantic_deleted']} points")
        except Exception as e:
            logger.warning(f"Semantic cache flush failed: {e}")
        
        return result
