"""
Multi-Provider LLM Wrapper for Education Chatbot
Supports Groq (Primary) and Gemini (Fallback)
Migrated to google-genai SDK (v1.0+)
"""

import os
import logging
from typing import Optional, List, Any
from pathlib import Path
from dotenv import load_dotenv

# Load environment
current_dir = Path(__file__).parent.parent
load_dotenv(dotenv_path=current_dir / ".env")

# New SDK
from google import genai
from google.genai import types

# Legacy SDK (Keep for backward compatibility during migration)
try:
    import google.generativeai as old_genai
    HAS_LEGACY_SDK = True
except ImportError:
    HAS_LEGACY_SDK = False

logger = logging.getLogger(__name__)

# Environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# Initialize Legacy Global State (Temporary)
if GEMINI_API_KEY and HAS_LEGACY_SDK:
    old_genai.configure(api_key=GEMINI_API_KEY)
    logger.info("✅ Legacy Gemini SDK configured (Backward Compatibility)")

# Import types
from .types import LLMResponse


class MultiProviderLLM:
    """
    Multi-provider LLM wrapper with automatic fallback:
    1. Groq (Primary)
    2. Gemini (Fallback)
    
    Uses google-genai SDK (Client-based) but syncs with legacy global config.
    """
    
    def __init__(self, category: str = "school", gemini_model: str = "gemini-2.5-flash"):
        self.category = category
        self.groq_model = GROQ_MODEL
        self.gemini_model_name = gemini_model
        self.gemini_client = None
        self.embeddings_available = True
        
        # Try to load keys from Firestore first (unless disabled)
        if os.getenv("DISABLE_FIRESTORE", "0") == "1":
            self.groq_keys = [GROQ_API_KEY] if GROQ_API_KEY and GROQ_API_KEY != "your_groq_api_key_here" else []
            self.gemini_keys = [GEMINI_API_KEY] if GEMINI_API_KEY else []
            self.groq_key_index = 0
            self.gemini_key_index = 0
            logger.info("⚠️ Firestore disabled via env. Using .env keys only.")
        else:
            self._load_keys_from_firestore()
        
        # Initialize Gemini Client
        self._init_gemini_client()
    
    def _load_keys_from_firestore(self):
        """Load API keys from Firestore (synced with Admin Panel) with rotation support"""
        try:
            import sys
            # Ensure backend directory is in path for firebase_config import
            backend_dir = str(current_dir)
            if backend_dir not in sys.path:
                sys.path.insert(0, backend_dir)
            
            # Direct import from firebase_config module
            from firebase_config import get_unified_groq_keys, get_unified_gemini_keys, config_loader

            # Get list of keys - Use UNIFIED mode to merge all keys from all categories
            self.groq_keys = get_unified_groq_keys()
            self.gemini_keys = get_unified_gemini_keys()
            
            # Load Groq model from Admin Panel config
            if config_loader:
                self.groq_model = config_loader.get_groq_model()
                logger.info(f"🤖 Groq model from config: {self.groq_model}")
            
            # Shuffle keys to distribute load and avoid "dead head-of-line" blocking
            import random
            
            if self.groq_keys:
                random.shuffle(self.groq_keys)
                logger.info(f"✅ Loaded {len(self.groq_keys)} Groq keys (unified & shuffled)")
            else:
                # Fallback to .env single key
                env_key = GROQ_API_KEY
                if env_key and env_key != "your_groq_api_key_here":
                    self.groq_keys = [env_key]
                    logger.info("✅ Loaded 1 Groq key from .env")
                else:
                    self.groq_keys = []
            
            self.groq_key_index = 0

            # Setup Gemini keys
            if not self.gemini_keys and GEMINI_API_KEY:
                 self.gemini_keys = [GEMINI_API_KEY]
                 logger.info("✅ Gemini key loaded from .env")
            elif self.gemini_keys:
                random.shuffle(self.gemini_keys)
                logger.info(f"✅ Loaded {len(self.gemini_keys)} Gemini keys (unified & shuffled)")
                
            self.gemini_key_index = 0
                
        except Exception as e:
            logger.warning(f"⚠️ Firestore config load failed: {e}")
            self.groq_keys = [GROQ_API_KEY] if GROQ_API_KEY else []
            self.gemini_keys = [GEMINI_API_KEY] if GEMINI_API_KEY else []
            self.groq_key_index = 0
            self.gemini_key_index = 0

    def _get_next_groq_key(self) -> Optional[str]:
        """Get next Groq key in rotation"""
        if not self.groq_keys:
            return None
        
        key = self.groq_keys[self.groq_key_index]
        self.groq_key_index = (self.groq_key_index + 1) % len(self.groq_keys)
        return key

    def _get_current_gemini_key(self) -> Optional[str]:
        if not getattr(self, 'gemini_keys', []):
            return None
        return self.gemini_keys[self.gemini_key_index]

    def _rotate_gemini_key(self):
        """Rotate to next Gemini key and re-init client"""
        if not getattr(self, 'gemini_keys', []):
            return
            
        self.gemini_key_index = (self.gemini_key_index + 1) % len(self.gemini_keys)
        self._init_gemini_client()

    def _init_gemini_client(self):
        """Initialize Gemini Client with current key (and sync legacy config)"""
        current_key = self._get_current_gemini_key()
        if not current_key:
            return

        try:
            # 1. New SDK Client
            self.gemini_client = genai.Client(api_key=current_key)
            logger.info(f"✅ Gemini Client ready (key: ...{current_key[-4:]})")
            
            # 2. Sync Legacy Global Config (for unmigrated modules)
            if HAS_LEGACY_SDK:
                old_genai.configure(api_key=current_key)
                # logger.debug("Synced legacy Gemini config")
                
        except Exception as e:
            logger.error(f"Failed to init Gemini Client: {e}")

    def _reload_keys_if_needed(self):
        """Hot-reload keys from shared_config.json if changed"""
        try:
            import json
            config_path = Path(__file__).parent.parent / 'shared_config.json'
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                api_keys = config.get('apiKeys', {}).get(self.category, {})
                new_groq_keys = [k for k in api_keys.get('groqKeys', []) if k and k.strip()]
                new_gemini_keys = [k for k in api_keys.get('geminiKeys', []) if k and k.strip()]
                
                if new_groq_keys and new_groq_keys != self.groq_keys:
                    self.groq_keys = new_groq_keys
                    self.groq_key_index = 0
                    logger.info(f"🔄 Hot-reloaded {len(new_groq_keys)} Groq keys")
                if new_gemini_keys and new_gemini_keys != self.gemini_keys:
                    self.gemini_keys = new_gemini_keys
                    self.gemini_key_index = 0
                    self._init_gemini_client()
                    logger.info(f"🔄 Hot-reloaded {len(new_gemini_keys)} Gemini keys")
        except Exception as e:
            pass

    def generate_content(self, prompt: str, timeout: int = 30, **kwargs) -> LLMResponse:
        """Generate content using Groq first, then Gemini as fallback"""
        
        self._reload_keys_if_needed()
        
        # 1. Try Groq (Primary) - Limit retries to avoid excessive waiting
        if self.groq_keys:
            max_retries = len(self.groq_keys)  # ⚡ IMPACT: Try ALL keys (User has many)
            for i in range(max_retries):
                current_key = self._get_next_groq_key()
                try:
                    response = self._call_groq(prompt, current_key, timeout)
                    if response:
                        return LLMResponse(text=response, provider="groq")
                except Exception as e:
                    error_str = str(e)
                    if i < max_retries - 1:
                         logger.warning(f"⚠️ Groq attempt {i+1} failed ({str(e)[:50]}...), rotating key...")
                         # ⚡ FAST ROTATION: No need to wait 5s if we have a fresh key
                         import time
                         time.sleep(0.5)  # Brief pause only

        
        # 2. Fallback to Gemini (Secondary)
        if self.gemini_keys:
            max_gemini_retries = len(self.gemini_keys)
            for i in range(max_gemini_retries):
                try:
                    if not self.gemini_client:
                        self._init_gemini_client()
                        
                    logger.info(f"⚡ Trying Gemini fallback (Attempt {i+1}/{max_gemini_retries})")
                    
                    # New SDK Usage
                    response = self.gemini_client.models.generate_content(
                        model=self.gemini_model_name,
                        contents=prompt
                    )
                    return LLMResponse(text=response.text, provider="gemini")
                        
                except Exception as e:
                     error_str = str(e)
                     logger.warning(f"⚠️ Gemini attempt {i+1} failed: {e}")
                     if i < max_gemini_retries - 1:
                         self._rotate_gemini_key()
                         # Backoff delay: wait before retrying (2, 4, 8... seconds)
                         import time
                         delay = min(2 ** (i + 1), 10)  # Max 10 seconds
                         if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str:
                             delay = 15  # Wait longer for rate limit
                             logger.info(f"⏳ Rate limit hit, waiting {delay}s before retry...")
                         time.sleep(delay)
                     else:
                         logger.error("❌ All Gemini keys exhausted")
                         raise e
        
        raise Exception("All providers and keys failed")
    
    def embed_content(self, content: str, model: str = "models/gemini-embedding-001") -> List[float]:
        """Generate embeddings using Gemini (with rotation support)"""
        if not self.embeddings_available:
            return []
        # Ensure client is ready
        if not self.gemini_client:
             self._init_gemini_client()
             
        if not self.gemini_keys:
            return []

        max_retries = len(self.gemini_keys)
        for i in range(max_retries):
            try:
                if model and not model.startswith("models/"):
                    model = f"models/{model}"
                # New SDK Usage for Embeddings
                response = self.gemini_client.models.embed_content(
                    model=model,
                    contents=content,
                    config={'output_dimensionality': 768}
                )
                return response.embeddings[0].values
            except Exception as e:
                logger.warning(f"⚠️ Embedding attempt {i+1} failed: {e}")
                err_str = str(e)
                # If model not found / not supported, disable embeddings to avoid repeated failures
                if "NOT_FOUND" in err_str or "not found" in err_str:
                    logger.error("❌ Embedding model unavailable; disabling embeddings for this process")
                    self.embeddings_available = False
                    return []
                if i < max_retries - 1:
                    self._rotate_gemini_key()
                else:
                    logger.error("❌ All embedding attempts failed")
                    return []
        return []

    def _call_groq(self, prompt: str, api_key: str, timeout: int = 30) -> Optional[str]:
        """Call Groq API with specific key"""
        import requests
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.groq_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2048,
            "temperature": 0.7
        }
        
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=timeout
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")
        elif response.status_code == 429:
            raise Exception("Rate limit exceeded")
        else:
            return None
