"""
Firebase Admin SDK integration for fetching shared config from Firestore.
Syncs with Admin Panel config so backend and frontend use the same API keys.

📄 ชื่อไฟล์: firebase_config.py
📝 คำอธิบาย:
   ตัวโหลดค่าตั้งค่าจาก Firebase Firestore (Config Loader)
   เพื่อให้ Backend (Python) ใช้ค่า Config เดียวกับ Frontend (React)

🛠 หน้าที่หลัก:
   1. Dynamic Config: โหลดค่า API Keys, Model Name จาก Firestore โดยไม่ต้องแก้โค้ด
   2. Shared Config: รองรับการอ่านไฟล์ shared_config.json (ถ้ามี)
   3. Key Rotation: ช่วยเลือก API Key ที่ดีที่สุดสำหรับแต่ละหมวด (โรงเรียน/นักเรียน)
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Default config if Firestore is not available
DEFAULT_CONFIG = {
    "apiKeys": {
        "general": {"groqKeys": [], "geminiKeys": []},
        "school": {"groqKeys": [], "geminiKeys": []},
        "student": {"groqKeys": [], "geminiKeys": []}
    }
}


class FirestoreConfigLoader:
    """
    Loads API keys and config from Firestore (Same as Admin Panel).
    Falls back to .env if Firestore is unavailable.
    """
    
    def __init__(self, project_id: str = "chatbot-97475"):
        self.project_id = project_id
        self.db = None
        self.config_cache: Dict[str, Any] = {}
        self.last_fetch_time = 0
        self.cache_ttl = 300  # 5 minutes
        
        self._init_firebase()
    
    def _init_firebase(self):
        """Initialize Firebase Admin SDK"""
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore
            
            # Check if already initialized
            try:
                firebase_admin.get_app()
                logger.info("✅ Firebase already initialized")
            except ValueError:
                # Initialize with project ID only (uses Application Default Credentials)
                try:
                    # First try with service account if exists
                    service_account_path = Path(__file__).parent / "serviceAccountKey.json"
                    if service_account_path.exists():
                        cred = credentials.Certificate(str(service_account_path))
                        firebase_admin.initialize_app(cred)
                        logger.info("✅ Firebase initialized with service account")
                    else:
                        # Use project ID directly (for development)
                        firebase_admin.initialize_app(options={"projectId": self.project_id})
                        logger.info(f"✅ Firebase initialized with project: {self.project_id}")
                except Exception as e:
                    logger.warning(f"⚠️ Firebase init failed: {e}")
                    return
            
            self.db = firestore.client()
            logger.info("✅ Firestore client ready")
            
        except ImportError:
            logger.warning("⚠️ firebase-admin not installed")
        except Exception as e:
            logger.warning(f"⚠️ Firestore connection failed: {e}")
    
    def get_config(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get config from Firestore, shared_config.json, or cache"""
        import time
        import json as json_module
        
        # Use cache if valid
        if not force_refresh and self.config_cache:
            if time.time() - self.last_fetch_time < self.cache_ttl:
                return self.config_cache
        
        # ========================================
        # PRIORITY 1: Firestore (synced from Admin Panel)
        # ========================================
        if self.db:
            try:
                doc_ref = self.db.collection("settings").document("main-config")
                doc = doc_ref.get()
                
                if doc.exists:
                    self.config_cache = doc.to_dict()
                    self.last_fetch_time = time.time()
                    logger.info("✅ Config loaded from Firestore (Admin Panel)")
                    return self.config_cache
            except Exception as e:
                logger.warning(f"⚠️ Failed to fetch from Firestore: {e}")
        
        # ========================================
        # PRIORITY 2: Fallback to shared_config.json
        # ========================================
        shared_config_path = Path(__file__).parent / 'shared_config.json'
        if shared_config_path.exists():
            try:
                with open(shared_config_path, 'r', encoding='utf-8') as f:
                    config = json_module.load(f)
                    if config.get('apiKeys'):
                        self.config_cache = config
                        self.last_fetch_time = time.time()
                        logger.info("✅ Config loaded from shared_config.json (fallback)")
                        return self.config_cache
            except Exception as e:
                logger.warning(f"⚠️ Failed to read shared_config.json: {e}")
        
        return DEFAULT_CONFIG
    
    def get_groq_keys(self, category: str = "school") -> List[str]:
        """Get Groq API keys for a category"""
        config = self.get_config()
        api_keys = config.get("apiKeys", {}).get(category, {})
        keys = api_keys.get("groqKeys", [])
        return [k for k in keys if k and k.strip()]
    
    def get_gemini_keys(self, category: str = "school") -> List[str]:
        """Get Gemini API keys for a category"""
        config = self.get_config()
        api_keys = config.get("apiKeys", {}).get(category, {})
        keys = api_keys.get("geminiKeys", [])
        return [k for k in keys if k and k.strip()]
    
    def get_best_groq_key(self, category: str = "school") -> Optional[str]:
        """Get the first available Groq key"""
        keys = self.get_groq_keys(category)
        return keys[0] if keys else None
    
    def get_best_gemini_key(self, category: str = "school") -> Optional[str]:
        """Get the first available Gemini key"""
        keys = self.get_gemini_keys(category)
        return keys[0] if keys else None
    
    def get_groq_model(self) -> str:
        """Get Groq model name from config, default to llama-3.3-70b-versatile"""
        config = self.get_config()
        # Try to get model from various possible locations
        model = config.get("model", {}).get("name")
        if not model:
            # Check if model is stored in apiKeys section
            for category in ["school", "general", "student"]:
                cat_config = config.get("apiKeys", {}).get(category, {})
                model = cat_config.get("groqModel")
                if model:
                    break
        return model or "llama-3.3-70b-versatile"


# Global config loader instance
config_loader: Optional[FirestoreConfigLoader] = None


def get_config_loader() -> FirestoreConfigLoader:
    """Get or create the global config loader"""
    global config_loader
    if config_loader is None:
        config_loader = FirestoreConfigLoader()
    return config_loader


def get_groq_key(category: str = "school") -> Optional[str]:
    """Convenience function to get Groq key"""
    loader = get_config_loader()
    return loader.get_best_groq_key(category)


def get_gemini_key(category: str = "school") -> Optional[str]:
    """Convenience function to get Gemini key"""
    loader = get_config_loader()
    return loader.get_best_gemini_key(category)


def get_groq_keys(category: str = "school") -> List[str]:
    """Get all Groq keys for rotation"""
    loader = get_config_loader()
    return loader.get_groq_keys(category)


def get_gemini_keys(category: str = "school") -> List[str]:
    """Get all Gemini keys for rotation"""
    loader = get_config_loader()
    return loader.get_gemini_keys(category)


def get_unified_groq_keys() -> List[str]:
    """Get all Groq keys from ALL categories for unified mode (deduplicated)"""
    loader = get_config_loader()
    all_keys = []
    seen = set()
    
    for category in ["general", "school", "student"]:
        keys = loader.get_groq_keys(category)
        for key in keys:
            if key and key not in seen:
                all_keys.append(key)
                seen.add(key)
    
    if all_keys:
        logger.info(f"🔑 Unified mode: {len(all_keys)} Groq keys from all categories")
    return all_keys


def get_unified_gemini_keys() -> List[str]:
    """Get all Gemini keys from ALL categories for unified mode (deduplicated)"""
    loader = get_config_loader()
    all_keys = []
    seen = set()
    
    for category in ["general", "school", "student"]:
        keys = loader.get_gemini_keys(category)
        for key in keys:
            if key and key not in seen:
                all_keys.append(key)
                seen.add(key)
    
    if all_keys:
        logger.info(f"🔑 Unified mode: {len(all_keys)} Gemini keys from all categories")
    return all_keys

