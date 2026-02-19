"""
Multi-Provider LLM Wrapper for Education Chatbot
Supports: Groq, Gemini, OpenAI, DeepSeek, Mistral, Together AI, OpenRouter
"""

import os
import logging
import random
import time
from typing import Optional, List, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

# Load environment
current_dir = Path(__file__).parent.parent
load_dotenv(dotenv_path=current_dir / ".env")

# Google SDKs
from google import genai
from google.genai import types

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

# Initialize Legacy Global State
if GEMINI_API_KEY and HAS_LEGACY_SDK:
    old_genai.configure(api_key=GEMINI_API_KEY)
    logger.info("✅ Legacy Gemini SDK configured (Backward Compatibility)")

from .types import LLMResponse

# ============================================================================
# Provider Registry — All OpenAI-compatible providers
# ============================================================================
PROVIDERS: Dict[str, Dict[str, str]] = {
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "default_model": "llama-3.3-70b-versatile",
        "label": "Groq",
    },
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "default_model": "gpt-4o-mini",
        "label": "OpenAI",
    },
    "deepseek": {
        "url": "https://api.deepseek.com/v1/chat/completions",
        "default_model": "deepseek-chat",
        "label": "DeepSeek",
    },
    "mistral": {
        "url": "https://api.mistral.ai/v1/chat/completions",
        "default_model": "mistral-small-latest",
        "label": "Mistral",
    },
    "together": {
        "url": "https://api.together.xyz/v1/chat/completions",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "label": "Together AI",
    },
    "openrouter": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "default_model": "meta-llama/llama-3.3-70b-instruct",
        "label": "OpenRouter",
    },
}

# Default priority order for fallback chain
DEFAULT_PROVIDER_PRIORITY = ["groq", "openai", "deepseek", "mistral", "together", "openrouter"]


class MultiProviderLLM:
    """
    Multi-provider LLM wrapper with automatic fallback.
    Tries providers in priority order, rotating keys within each provider.
    Gemini uses Google SDK separately (different API format).
    """
    
    def __init__(self, category: str = "school", gemini_model: str = "gemini-2.5-flash"):
        self.category = category
        self.groq_model = GROQ_MODEL
        self.gemini_model_name = gemini_model
        self.gemini_client = None
        self.embeddings_available = True
        
        # Provider keys: { "groq": ["key1", "key2"], "openai": ["key1"], ... }
        self.provider_keys: Dict[str, List[str]] = {}
        self.provider_key_indices: Dict[str, int] = {}
        self.provider_models: Dict[str, str] = {}
        
        # Gemini keys (separate because it uses Google SDK)
        self.gemini_keys: List[str] = []
        self.gemini_key_index = 0
        
        # Provider priority order
        self.provider_priority: List[str] = list(DEFAULT_PROVIDER_PRIORITY)
        
        # Load keys
        if os.getenv("DISABLE_FIRESTORE", "0") == "1":
            self._load_keys_from_env()
            logger.info("⚠️ Firestore disabled via env. Using .env keys only.")
        else:
            self._load_keys_from_firestore()
        
        # Initialize Gemini Client
        self._init_gemini_client()
        
        # Log active providers
        active = [p for p in self.provider_priority if self.provider_keys.get(p)]
        if self.gemini_keys:
            active.append("gemini")
        logger.info(f"✅ Using model: {' → '.join(active) if active else 'NONE'}")
    
    def _load_keys_from_env(self):
        """Load keys from environment variables only"""
        if GROQ_API_KEY and GROQ_API_KEY != "your_groq_api_key_here":
            self.provider_keys["groq"] = [GROQ_API_KEY]
            self.provider_key_indices["groq"] = 0
        
        if GEMINI_API_KEY:
            self.gemini_keys = [GEMINI_API_KEY]
        
        # Check for other provider keys in env
        for provider in ["openai", "deepseek", "mistral", "together", "openrouter"]:
            env_key = os.getenv(f"{provider.upper()}_API_KEY")
            if env_key and env_key != f"your_{provider}_api_key_here":
                self.provider_keys[provider] = [env_key]
                self.provider_key_indices[provider] = 0
    
    def _load_keys_from_firestore(self):
        """Load API keys from Firestore (synced with Admin Panel)"""
        try:
            import sys
            backend_dir = str(current_dir)
            if backend_dir not in sys.path:
                sys.path.insert(0, backend_dir)
            
            from firebase_config import get_unified_provider_keys, get_unified_gemini_keys, config_loader
            
            # Load all provider keys from Firestore
            for provider in PROVIDERS:
                keys = get_unified_provider_keys(provider)
                if keys:
                    random.shuffle(keys)
                    self.provider_keys[provider] = keys
                    self.provider_key_indices[provider] = 0
                    logger.info(f"✅ Loaded {len(keys)} {PROVIDERS[provider]['label']} keys (unified & shuffled)")
            
            # Fallback: if Groq keys empty, try env
            if not self.provider_keys.get("groq"):
                if GROQ_API_KEY and GROQ_API_KEY != "your_groq_api_key_here":
                    self.provider_keys["groq"] = [GROQ_API_KEY]
                    self.provider_key_indices["groq"] = 0
                    logger.info("✅ Loaded 1 Groq key from .env")
            
            # Load Gemini keys
            self.gemini_keys = get_unified_gemini_keys()
            if not self.gemini_keys and GEMINI_API_KEY:
                self.gemini_keys = [GEMINI_API_KEY]
                logger.info("✅ Gemini key loaded from .env")
            elif self.gemini_keys:
                random.shuffle(self.gemini_keys)
                logger.info(f"✅ Loaded {len(self.gemini_keys)} Gemini keys (unified & shuffled)")
            self.gemini_key_index = 0
            
            # Load Groq model from config
            if config_loader:
                self.groq_model = config_loader.get_groq_model()
                logger.info(f"🤖 Groq model from config: {self.groq_model}")
            
            # Load provider priority from config
            if config_loader:
                config = config_loader.get_config()
                priority = config.get("providerPriority")
                if priority and isinstance(priority, list):
                    self.provider_priority = priority
                    logger.info(f"📋 Provider priority: {' → '.join(priority)}")
                    
        except Exception as e:
            logger.warning(f"⚠️ Firestore config load failed: {e}")
            self._load_keys_from_env()
    
    def _get_next_key(self, provider: str) -> Optional[str]:
        """Get next key in rotation for a provider"""
        keys = self.provider_keys.get(provider, [])
        if not keys:
            return None
        idx = self.provider_key_indices.get(provider, 0)
        key = keys[idx]
        self.provider_key_indices[provider] = (idx + 1) % len(keys)
        return key

    def _get_current_gemini_key(self) -> Optional[str]:
        if not self.gemini_keys:
            return None
        return self.gemini_keys[self.gemini_key_index]

    def _rotate_gemini_key(self):
        """Rotate to next Gemini key and re-init client"""
        if not self.gemini_keys:
            return
        self.gemini_key_index = (self.gemini_key_index + 1) % len(self.gemini_keys)
        self._init_gemini_client()

    def _init_gemini_client(self):
        """Initialize Gemini Client with current key"""
        current_key = self._get_current_gemini_key()
        if not current_key:
            return
        try:
            self.gemini_client = genai.Client(api_key=current_key)
            logger.info(f"✅ Gemini Client ready (key: ...{current_key[-4:]})")
            if HAS_LEGACY_SDK:
                old_genai.configure(api_key=current_key)
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
                
                # Reload all provider keys
                for provider in PROVIDERS:
                    key_field = f"{provider}Keys"
                    new_keys = [k for k in api_keys.get(key_field, []) if k and k.strip()]
                    current_keys = self.provider_keys.get(provider, [])
                    if new_keys and new_keys != current_keys:
                        self.provider_keys[provider] = new_keys
                        self.provider_key_indices[provider] = 0
                        logger.info(f"🔄 Hot-reloaded {len(new_keys)} {provider} keys")
                
                # Reload Gemini keys
                new_gemini = [k for k in api_keys.get('geminiKeys', []) if k and k.strip()]
                if new_gemini and new_gemini != self.gemini_keys:
                    self.gemini_keys = new_gemini
                    self.gemini_key_index = 0
                    self._init_gemini_client()
                    logger.info(f"🔄 Hot-reloaded {len(new_gemini)} Gemini keys")
        except Exception:
            pass

    def generate_content(self, prompt: str, timeout: int = 30, **kwargs) -> LLMResponse:
        """Generate content using provider priority chain, then Gemini as final fallback"""
        
        self._reload_keys_if_needed()
        errors = []
        
        # 1. Try OpenAI-compatible providers in priority order
        for provider in self.provider_priority:
            keys = self.provider_keys.get(provider, [])
            if not keys:
                continue
            
            max_retries = len(keys)
            for i in range(max_retries):
                current_key = self._get_next_key(provider)
                try:
                    model = self.provider_models.get(provider) or PROVIDERS[provider]["default_model"]
                    # Special case: Groq uses its own model setting
                    if provider == "groq":
                        model = self.groq_model
                    
                    response = self._call_openai_compatible(
                        provider=provider,
                        api_key=current_key,
                        prompt=prompt,
                        model=model,
                        timeout=timeout
                    )
                    if response:
                        return LLMResponse(text=response, provider=provider)
                except Exception as e:
                    error_str = str(e)
                    errors.append(f"{provider}({i+1}): {error_str[:60]}")
                    if i < max_retries - 1:
                        logger.warning(f"⚠️ {PROVIDERS[provider]['label']} attempt {i+1} failed ({error_str[:50]}...), rotating key...")
                        time.sleep(0.5)
        
        # 2. Final fallback: Gemini (uses Google SDK, not OpenAI-compatible)
        if self.gemini_keys:
            max_gemini_retries = len(self.gemini_keys)
            for i in range(max_gemini_retries):
                try:
                    if not self.gemini_client:
                        self._init_gemini_client()
                    
                    logger.info(f"⚡ Trying Gemini fallback (Attempt {i+1}/{max_gemini_retries})")
                    response = self.gemini_client.models.generate_content(
                        model=self.gemini_model_name,
                        contents=prompt
                    )
                    return LLMResponse(text=response.text, provider="gemini")
                    
                except Exception as e:
                    error_str = str(e)
                    errors.append(f"gemini({i+1}): {error_str[:60]}")
                    logger.warning(f"⚠️ Gemini attempt {i+1} failed: {e}")
                    if i < max_gemini_retries - 1:
                        self._rotate_gemini_key()
                        delay = min(2 ** (i + 1), 10)
                        if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str:
                            delay = 15
                            logger.info(f"⏳ Rate limit hit, waiting {delay}s before retry...")
                        time.sleep(delay)
                    else:
                        logger.error("❌ All Gemini keys exhausted")
                        raise e
        
        raise Exception(f"All providers failed: {'; '.join(errors)}")
    
    def embed_content(self, content: str, model: str = "models/gemini-embedding-001") -> List[float]:
        """Generate embeddings using Gemini (with rotation support)"""
        if not self.embeddings_available:
            return []
        if not self.gemini_client:
            self._init_gemini_client()
        if not self.gemini_keys:
            return []

        max_retries = len(self.gemini_keys)
        for i in range(max_retries):
            try:
                if model and not model.startswith("models/"):
                    model = f"models/{model}"
                response = self.gemini_client.models.embed_content(
                    model=model,
                    contents=content,
                    config={'output_dimensionality': 768}
                )
                return response.embeddings[0].values
            except Exception as e:
                logger.warning(f"⚠️ Embedding attempt {i+1} failed: {e}")
                err_str = str(e)
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

    def _call_openai_compatible(self, provider: str, api_key: str, prompt: str, 
                                 model: str, timeout: int = 30) -> Optional[str]:
        """Call any OpenAI-compatible API (Groq, OpenAI, DeepSeek, Mistral, etc.)"""
        import requests
        
        provider_info = PROVIDERS.get(provider, {})
        url = provider_info.get("url")
        if not url:
            return None
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # OpenRouter requires extra headers
        if provider == "openrouter":
            headers["HTTP-Referer"] = "https://do-moe.moe.go.th"
            headers["X-Title"] = "DO-MOE Education Chatbot"
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2048,
            "temperature": 0.7
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")
        elif response.status_code == 429:
            raise Exception(f"Rate limit exceeded ({provider})")
        elif response.status_code == 401:
            raise Exception(f"Invalid API key ({provider})")
        else:
            raise Exception(f"HTTP {response.status_code} from {provider}")
