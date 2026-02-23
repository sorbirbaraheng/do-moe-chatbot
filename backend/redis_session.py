"""
Redis Session Storage for DO-MOE Chatbot
Production-grade session management with Redis

📄 ชื่อไฟล์: redis_session.py
📝 คำอธิบาย:
   ระบบจัดการ Session แบบ Production-grade ด้วย Redis
   รองรับ concurrent users และ auto-expire sessions

🛠 Features:
   1. In-memory storage (เร็วกว่า SQLite 10-100x)
   2. TTL (Time-To-Live) auto-expire sessions
   3. Connection pooling
   4. Fallback to SQLite if Redis unavailable
"""

import os
import json
import time
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Default TTL: 7 days
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", 7 * 24 * 60 * 60))

# Try to import Redis
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("⚠️ redis package not installed. Run: pip install redis")

# Redis connection pool (shared across all requests)
_redis_pool = None
_redis_client = None


def _get_sqlite_fallback_module():
    """Import SQLite fallback module in both package and script execution modes."""
    try:
        from . import session_db as sqlite_session_db  # package mode
        return sqlite_session_db
    except Exception:
        import session_db as sqlite_session_db  # script mode
        return sqlite_session_db


def get_redis_client():
    """Get Redis client with connection pooling"""
    global _redis_pool, _redis_client
    
    if not REDIS_AVAILABLE:
        return None
    
    if _redis_client is not None:
        return _redis_client
    
    try:
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        
        # Create connection pool
        _redis_pool = redis.ConnectionPool.from_url(
            redis_url,
            max_connections=20,
            decode_responses=True
        )
        
        _redis_client = redis.Redis(connection_pool=_redis_pool)
        
        # Test connection
        _redis_client.ping()
        logger.info(f"✅ Redis connected: {redis_url.split('@')[-1]}")  # Hide password
        
        return _redis_client
    except Exception as e:
        logger.warning(f"⚠️ Redis connection failed: {e}")
        return None


def init_db():
    """Initialize Redis connection (or fallback to SQLite)"""
    client = get_redis_client()
    if client:
        logger.info("✅ Redis Session Storage initialized")
    else:
        logger.warning("⚠️ Redis unavailable, falling back to SQLite")
        sqlite_session_db = _get_sqlite_fallback_module()
        sqlite_session_db.init_db()


def get_session_data(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve session memory from Redis"""
    client = get_redis_client()
    
    if client:
        try:
            key = f"session:{session_id}"
            data = client.get(key)
            
            if data:
                # Refresh TTL on access (sliding expiration)
                client.expire(key, SESSION_TTL_SECONDS)
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Redis read error: {e}")
    
    # Fallback to SQLite
    try:
        sqlite_session_db = _get_sqlite_fallback_module()
        return sqlite_session_db.get_session_data(session_id)
    except Exception:
        return None


def save_session_data(session_id: str, memory_data: Dict[str, Any]):
    """Save session memory to Redis with TTL"""
    client = get_redis_client()
    
    if client:
        try:
            key = f"session:{session_id}"
            json_str = json.dumps(memory_data, ensure_ascii=False)
            
            # SETEX = SET with EXpire
            client.setex(key, SESSION_TTL_SECONDS, json_str)
            return
        except Exception as e:
            logger.error(f"Redis write error: {e}")
    
    # Fallback to SQLite
    try:
        sqlite_session_db = _get_sqlite_fallback_module()
        sqlite_session_db.save_session_data(session_id, memory_data)
    except Exception:
        pass


def delete_session(session_id: str):
    """Delete a specific session"""
    client = get_redis_client()
    
    if client:
        try:
            key = f"session:{session_id}"
            client.delete(key)
            return
        except Exception as e:
            logger.error(f"Redis delete error: {e}")


def get_session_count() -> int:
    """Get total active session count"""
    client = get_redis_client()
    
    if client:
        try:
            keys = client.keys("session:*")
            return len(keys)
        except:
            pass
    return 0


def cleanup_old_sessions(days: int = 7):
    """
    Cleanup old sessions (Redis handles this automatically via TTL)
    This function is mainly for SQLite fallback
    """
    client = get_redis_client()
    
    if client:
        # Redis auto-expires with TTL, nothing to do
        logger.info("🧹 Redis uses auto-expire TTL, no cleanup needed")
        return
    
    # SQLite fallback
    try:
        sqlite_session_db = _get_sqlite_fallback_module()
        sqlite_session_db.cleanup_old_sessions(days)
    except Exception:
        pass


# Export same interface as session_db for drop-in replacement
__all__ = [
    'init_db',
    'get_session_data', 
    'save_session_data',
    'delete_session',
    'get_session_count',
    'cleanup_old_sessions'
]
