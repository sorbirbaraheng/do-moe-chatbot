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
    
    def __init__(self, client, collection_name: str = "semantic_cache"):
        from qdrant_client.models import VectorParams, Distance, PointStruct
        
        self.client = client
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

    def check(self, query: str) -> Optional[str]:
        """Check cache for similar queries"""
        try:
            import google.generativeai as genai
            
            # Generate embedding for the query
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=query,
                task_type="retrieval_query"
            )
            vector = result['embedding']
            
            # Use new query_points API (qdrant-client >= 1.7.0)
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=vector,
                limit=1
            )
            hits = response.points
            
            if hits and hits[0].score >= self.threshold:
                logger.info(f"⚡ Cache Hit! Score: {hits[0].score:.4f}")
                return hits[0].payload.get("response")
                
        except Exception as e:
            logger.warning(f"Cache check failed: {e}")
        return None

    def save(self, query: str, response: str):
        """Save response to cache"""
        try:
            import uuid
            import google.generativeai as genai
            
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=query,
                task_type="retrieval_query"
            )
            vector = result['embedding']
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    self.PointStruct(
                        id=str(uuid.uuid4()),
                        vector=vector,
                        payload={"query": query, "response": response, "timestamp": time.time()}
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
    
    def __init__(self, qdrant_client):
        self.semantic_cache = SemanticCache(qdrant_client)
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
    
    def _get_cache_key(self, query: str) -> str:
        """Generate Redis key from query"""
        normalized = self._normalize_query(query)
        hash_val = hashlib.md5(normalized.encode()).hexdigest()[:16]
        return f"domoe:cache:{hash_val}"
    
    def check(self, query: str) -> Optional[str]:
        """Check cache: Redis first, then Semantic"""
        # L1: Try Redis (fast exact match)
        if self.redis_client:
            try:
                cache_key = self._get_cache_key(query)
                cached = self.redis_client.get(cache_key)
                if cached:
                    logger.info("⚡ Redis L1 Cache Hit!")
                    return cached
            except Exception as e:
                logger.warning(f"Redis check failed: {e}")
        
        # L2: Try Semantic Cache
        return self.semantic_cache.check(query)
    
    def save(self, query: str, response: str):
        """Save to both caches"""
        # Save to Redis (L1)
        if self.redis_client:
            try:
                cache_key = self._get_cache_key(query)
                self.redis_client.setex(cache_key, self.ttl, response)
            except Exception as e:
                logger.warning(f"Redis save failed: {e}")
        
        # Save to Semantic Cache (L2)
        self.semantic_cache.save(query, response)
