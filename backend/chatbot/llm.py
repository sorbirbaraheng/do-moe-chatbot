"""
Multi-Provider LLM Wrapper for Education Chatbot
Supports Groq (Primary) and Gemini (Fallback)
"""

import os
import logging
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

# Load environment
current_dir = Path(__file__).parent.parent
load_dotenv(dotenv_path=current_dir / ".env")

import google.generativeai as genai

logger = logging.getLogger(__name__)

# Environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Initialize Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info("✅ Gemini API configured (Fallback)")

# Import types
from .types import LLMResponse


class MultiProviderLLM:
    """
    Multi-provider LLM wrapper with automatic fallback:
    1. Groq (Primary) - Faster, generous free tier
    2. Gemini (Fallback) - When Groq fails
    
    API keys are fetched from Firestore (Admin Panel config) for consistency.
    Falls back to .env if Firestore is unavailable.
    """
    
    def __init__(self, category: str = "school", gemini_model: str = 'gemini-2.0-flash-exp'):
        self.category = category
        self.groq_model = GROQ_MODEL
        self.gemini_model_name = gemini_model
        self.gemini_model = None
        
        # Try to load keys from Firestore first
        self._load_keys_from_firestore()
        
        self._init_gemini(gemini_model)
    
    def _load_keys_from_firestore(self):
        """Load API keys from Firestore (synced with Admin Panel) with rotation support"""
        try:
            import sys
            # Ensure backend directory is in path for firebase_config import
            backend_dir = str(current_dir)
            if backend_dir not in sys.path:
                sys.path.insert(0, backend_dir)
            
            # Direct import from firebase_config module
            from firebase_config import get_groq_keys, get_gemini_keys


            # Get list of keys
            self.groq_keys = get_groq_keys(self.category)
            self.gemini_keys = get_gemini_keys(self.category)
            
            self.groq_key_index = 0
            
            if self.groq_keys:
                logger.info(f"✅ Loaded {len(self.groq_keys)} Groq keys from Firestore (category: {self.category})")
            else:
                # Fallback to .env single key
                env_key = GROQ_API_KEY
                if env_key and env_key != "your_groq_api_key_here":
                    self.groq_keys = [env_key]
                    logger.info("✅ Loaded 1 Groq key from .env")
                else:
                    self.groq_keys = []
            
            if self.gemini_keys:
                # Use first Gemini key for now, could implement rotation later if needed
                genai.configure(api_key=self.gemini_keys[0])
                logger.info(f"✅ Loaded {len(self.gemini_keys)} Gemini keys from Firestore (category: {self.category})")
            elif GEMINI_API_KEY:
                 genai.configure(api_key=GEMINI_API_KEY)
                 logger.info("✅ Gemini key loaded from .env")
                
        except Exception as e:
            logger.warning(f"⚠️ Firestore config load failed: {e}")
            self.groq_keys = [GROQ_API_KEY] if GROQ_API_KEY else []
            self.groq_key_index = 0

    def _get_next_groq_key(self) -> Optional[str]:
        """Get next Groq key in rotation"""
        if not self.groq_keys:
            return None
        
        key = self.groq_keys[self.groq_key_index]
        # Rotate index
        self.groq_key_index = (self.groq_key_index + 1) % len(self.groq_keys)
        return key

    def _init_gemini(self, model_name: str):
        """Initialize Gemini as fallback"""
        try:
            if not model_name.startswith('models/'):
                model_name = f'models/{model_name}'
            self.gemini_model = genai.GenerativeModel(model_name)
            logger.info(f"✅ Gemini fallback ready: {model_name}")
        except Exception as e:
            logger.error(f"Failed to init Gemini: {e}")
    
    def generate_content(self, prompt: str, timeout: int = 30, **kwargs) -> LLMResponse:
        """Generate content using Groq first (with key rotation), then Gemini as fallback"""
        # Note: **kwargs absorbs arguments like 'stream' that might be passed but not supported yet
        
        # Try Groq first
        if self.groq_keys:
            # Try ALL available keys before giving up
            max_retries = len(self.groq_keys) 
            
            for i in range(max_retries):
                current_key = self._get_next_groq_key()
                try:
                    response = self._call_groq(prompt, current_key, timeout)
                    if response:
                        return LLMResponse(text=response, provider="groq")
                except Exception as e:
                    # Only log warning if it's not the last retry
                    if i < max_retries - 1:
                         logger.warning(f"⚠️ Groq attempt {i+1} failed ({str(e)[:50]}...), retrying with next key...")
                    else:
                         logger.warning(f"⚠️ Groq all attempts failed: {e}")
        
        # Fallback to Gemini
        try:
            if self.gemini_model:
                logger.info("⚡ Falling back to Gemini...")
                response = self.gemini_model.generate_content(prompt)
                return LLMResponse(text=response.text, provider="gemini")
        except Exception as e:
            logger.error(f"❌ Gemini fallback also failed: {e}")
            raise
    
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
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            logger.info(f"⚡ Groq responded ({self.groq_model})")
            return content
        elif response.status_code == 429:
            logger.warning("⚠️ Groq rate limited (429) - Switching key...")
            # Raise exception to trigger next key retry
            raise Exception("Rate limit exceeded")
        else:
            logger.warning(f"⚠️ Groq error: {response.status_code}")
            return None
