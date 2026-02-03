
import logging
from typing import Optional, Dict, Any
import time

# Import shared Firebase config loader
try:
    from backend.firebase_config import get_config_loader
except ImportError:
    # Fallback if running from a different directory (e.g. tests)
    import sys
    sys.path.append("..")
    from backend.firebase_config import get_config_loader

logger = logging.getLogger(__name__)

SESSION_COLLECTION = "user_sessions"
SESSION_TTL = 3600 * 24  # 24 hours expiry/TTL

def get_db():
    """Get Firestore client from shared config loader"""
    loader = get_config_loader()
    return loader.db

def get_session_data(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve session memory dictionary from Firestore"""
    try:
        db = get_db()
        if not db:
            logger.warning("⚠️ Firestore not available for sessions")
            return None
            
        doc_ref = db.collection(SESSION_COLLECTION).document(session_id)
        doc = doc_ref.get()
        
        if doc.exists:
            data = doc.to_dict()
            logger.info(f"📥 Loaded session {session_id} from Firestore")
            return data.get('memory', {})
        
        return None
        
    except Exception as e:
        logger.error(f"⚠️ Firestore Read Error for session {session_id}: {e}")
        return None

def save_session_data(session_id: str, memory_data: Dict[str, Any]):
    """Save or update session memory in Firestore"""
    try:
        db = get_db()
        if not db:
            return
            
        doc_ref = db.collection(SESSION_COLLECTION).document(session_id)
        timestamp = time.time()
        
        # Save nested 'memory' object to keep document clean
        payload = {
            'memory': memory_data,
            'updated_at': timestamp,
            'session_id': session_id
        }
        
        doc_ref.set(payload, merge=True)
        # logger.info(f"💾 Saved session {session_id} to Firestore")
        
    except Exception as e:
        logger.error(f"⚠️ Firestore Write Error for session {session_id}: {e}")
