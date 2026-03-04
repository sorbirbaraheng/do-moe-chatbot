"""
Input Sanitization and Security for Education Chatbot

📄 ชื่อไฟล์: security.py
📝 คำอธิบาย:
   ระบบรักษาความปลอดภัยสำหรับ input ผู้ใช้
   - ตรวจสอบ Prompt Injection (LLM attacks)
   - ตรวจสอบ SQL / NoSQL Injection
   - ตรวจสอบ Path Traversal
   - ตรวจสอบ XSS (HTML Injection)
   - Brute-force protection สำหรับ admin login
"""

import re
import time
import logging
import threading
from typing import Tuple, Optional, Dict

logger = logging.getLogger(__name__)


class InputSanitizer:
    """Security layer for input validation and sanitization"""
    
    # Configuration
    MAX_LENGTH = 1000
    MIN_LENGTH = 1
    
    # Common prompt injection patterns (LLM-specific)
    INJECTION_PATTERNS = [
        r"ignore\s*(all\s*)?(previous|above)\s*(instructions?|prompts?)",
        r"forget\s*(everything|all|your)\s*(you|instructions?)?",
        r"you\s*are\s*(now|a)\s*(new|different|evil)",
        r"pretend\s*(to\s*be|you\s*are)",
        r"disregard\s*(all|previous|your)",
        r"override\s*(your|the)\s*(instructions?|programming)",
        r"jailbreak",
        r"DAN\s*mode",
        r"\[system\]",
        r"\[INST\]",
        r"<\|.*?\|>",
        r"act\s*as\s*(if|a|an)\s*(you|unrestricted|unfiltered)",
        r"bypass\s*(your|the|any)\s*(filter|restriction|guard|safety)",
        r"reveal\s*(your|the)\s*(system|initial|original)\s*(prompt|instruction)",
        r"what\s*(is|are)\s*your\s*(system|initial|original)\s*(prompt|instruction)",
        r"repeat\s*(the|your)\s*(system|above)\s*(prompt|instruction|text)",
    ]
    
    # SQL / NoSQL injection patterns
    SQL_PATTERNS = [
        r"(?:--|;)\s*(DROP|ALTER|DELETE|TRUNCATE|UPDATE|INSERT)\s",
        r"'\s*(OR|AND)\s*'?\d*'?\s*=\s*'?\d*",
        r"UNION\s+(ALL\s+)?SELECT",
        r"INTO\s+(OUT|DUMP)FILE",
        r"LOAD_FILE\s*\(",
        r"\bEXEC(UTE)?\s*\(",
        r"xp_cmdshell",
        r"\$where\s*:",         # MongoDB injection
        r"\$regex\s*:",         # MongoDB regex injection
        r"\$gt\s*:",            # MongoDB operator injection
        r"\$ne\s*:",
    ]
    
    # Path traversal patterns
    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./",
        r"\.\.\\",
        r"%2e%2e[/\\]",
        r"%252e%252e",
        r"/etc/passwd",
        r"/etc/shadow",
        r"C:\\Windows",
    ]
    
    # XSS patterns (HTML/JS injection)
    XSS_PATTERNS = [
        r"<script[\s>]",
        r"javascript\s*:",
        r"on(load|error|click|mouseover)\s*=",
        r"<iframe[\s>]",
        r"<object[\s>]",
        r"<embed[\s>]",
        r"<svg[\s>].*?on\w+\s*=",
        r"eval\s*\(",
        r"document\.(cookie|location|write)",
        r"window\.(location|open)",
    ]
    
    def __init__(self):
        self.injection_regex = re.compile(
            '|'.join(self.INJECTION_PATTERNS), 
            re.IGNORECASE
        )
        self.sql_regex = re.compile(
            '|'.join(self.SQL_PATTERNS),
            re.IGNORECASE
        )
        self.path_regex = re.compile(
            '|'.join(self.PATH_TRAVERSAL_PATTERNS),
            re.IGNORECASE
        )
        self.xss_regex = re.compile(
            '|'.join(self.XSS_PATTERNS),
            re.IGNORECASE
        )
    
    def sanitize(self, query: str) -> Tuple[str, Optional[str]]:
        """
        Sanitize user input.
        Returns: (sanitized_query, error_message)
        If error_message is not None, the input should be rejected.
        """
        if not query:
            return "", "❌ กรุณาพิมพ์ข้อความครับ"
        
        # Strip whitespace
        query = query.strip()
        
        # Check minimum length
        if len(query) < self.MIN_LENGTH:
            return "", "❌ กรุณาพิมพ์ข้อความครับ"
        
        # Check maximum length
        if len(query) > self.MAX_LENGTH:
            return "", f"❌ ข้อความยาวเกินไป (สูงสุด {self.MAX_LENGTH} ตัวอักษร)"
        
        # Detect prompt injection
        if self.detect_injection(query):
            logger.warning(f"🚨 Prompt injection attempt detected: {query[:80]}...")
            return "", "🛡️ ขออภัยครับ ข้อความนี้ไม่สามารถประมวลผลได้ กรุณาถามใหม่อีกครั้งครับ"
        
        # Detect SQL/NoSQL injection
        if self.sql_regex.search(query):
            logger.warning(f"🚨 SQL/NoSQL injection attempt: {query[:80]}...")
            return "", "🛡️ ขออภัยครับ ข้อความนี้ไม่สามารถประมวลผลได้ กรุณาถามใหม่อีกครั้งครับ"
        
        # Detect path traversal
        if self.path_regex.search(query):
            logger.warning(f"🚨 Path traversal attempt: {query[:80]}...")
            return "", "🛡️ ขออภัยครับ ข้อความนี้ไม่สามารถประมวลผลได้ กรุณาถามใหม่อีกครั้งครับ"
        
        # Detect XSS
        if self.xss_regex.search(query):
            logger.warning(f"🚨 XSS attempt detected: {query[:80]}...")
            return "", "🛡️ ขออภัยครับ ข้อความนี้ไม่สามารถประมวลผลได้ กรุณาถามใหม่อีกครั้งครับ"
        
        # Basic sanitization: remove control characters (keep newlines/tabs)
        query = ''.join(char for char in query if ord(char) >= 32 or char in '\n\t')
        
        # Remove null bytes
        query = query.replace('\x00', '')
        
        return query, None
    
    def detect_injection(self, query: str) -> bool:
        """Detect common prompt injection patterns"""
        return bool(self.injection_regex.search(query))
    
    @staticmethod
    def escape_html(text: str) -> str:
        """Escape HTML entities to prevent XSS"""
        if not text:
            return text
        html_escape_table = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#x27;",
        }
        for char, escaped in html_escape_table.items():
            text = text.replace(char, escaped)
        return text


class BruteForceProtection:
    """
    IP-based brute-force protection for admin login.
    Blocks IP after too many failed attempts within a time window.
    """
    
    def __init__(self, max_attempts: int = 5, window_seconds: int = 300, lockout_seconds: int = 900):
        self.max_attempts = max_attempts        # 5 attempts
        self.window_seconds = window_seconds    # within 5 minutes
        self.lockout_seconds = lockout_seconds  # lock for 15 minutes
        self._attempts: Dict[str, list] = {}    # ip -> [timestamp, ...]
        self._lockouts: Dict[str, float] = {}   # ip -> lockout_until timestamp
        self._lock = threading.Lock()
    
    def is_locked(self, ip: str) -> bool:
        """Check if an IP is currently locked out"""
        with self._lock:
            lockout_until = self._lockouts.get(ip, 0)
            if lockout_until > time.time():
                return True
            elif lockout_until > 0:
                # Lockout expired — clean up
                del self._lockouts[ip]
                self._attempts.pop(ip, None)
            return False
    
    def record_failure(self, ip: str) -> bool:
        """
        Record a failed login attempt.
        Returns True if the IP is now locked out.
        """
        now = time.time()
        with self._lock:
            if ip not in self._attempts:
                self._attempts[ip] = []
            
            # Remove stale attempts outside the window
            self._attempts[ip] = [t for t in self._attempts[ip] if now - t < self.window_seconds]
            self._attempts[ip].append(now)
            
            if len(self._attempts[ip]) >= self.max_attempts:
                self._lockouts[ip] = now + self.lockout_seconds
                logger.warning(f"🔒 IP {ip} locked out for {self.lockout_seconds}s after {len(self._attempts[ip])} failed attempts")
                return True
            return False
    
    def record_success(self, ip: str):
        """Clear attempts after successful login"""
        with self._lock:
            self._attempts.pop(ip, None)
            self._lockouts.pop(ip, None)
    
    def remaining_seconds(self, ip: str) -> int:
        """Get remaining lockout seconds for an IP"""
        with self._lock:
            lockout_until = self._lockouts.get(ip, 0)
            remaining = lockout_until - time.time()
            return max(0, int(remaining))


class UserRateLimiter:
    """
    Per-user rate limiting — inspired by ChatGPT/Claude/Gemini.
    Uses Redis for atomic counters with TTL-based sliding windows.
    Falls back to in-memory dict if Redis is unavailable.

    Quota tiers:
      - admin     → unlimited
      - user      → configurable daily/hourly limits
      - anonymous → stricter daily/hourly limits (keyed by IP)
    """

    # Default quotas (overridable by env vars)
    DEFAULT_QUOTAS = {
        "admin":     {"daily": 0, "hourly": 0},          # 0 = unlimited
        "user":      {"daily": 50, "hourly": 20},
        "anonymous": {"daily": 10, "hourly": 5},
    }

    # TTL for each window
    WINDOW_TTL = {
        "daily":  86400,   # 24h
        "hourly": 3600,    # 1h
    }

    def __init__(self):
        import os
        self.quotas: Dict[str, Dict[str, int]] = {}
        for role in ("admin", "user", "anonymous"):
            daily_env = f"RATE_LIMIT_{role.upper()}_DAILY"
            hourly_env = f"RATE_LIMIT_{role.upper()}_HOURLY"
            self.quotas[role] = {
                "daily": int(os.getenv(daily_env, self.DEFAULT_QUOTAS[role]["daily"])),
                "hourly": int(os.getenv(hourly_env, self.DEFAULT_QUOTAS[role]["hourly"])),
            }
        # In-memory fallback when Redis is not available
        self._mem_counters: Dict[str, Dict[str, int]] = {}    # key -> {"count": n, "expires": ts}
        self._mem_lock = threading.Lock()
        self._redis_client = None
        self._redis_checked = False

    def _get_redis(self):
        """Lazy-load Redis client from the session module."""
        if not self._redis_checked:
            self._redis_checked = True
            try:
                from redis_session import get_redis_client
                self._redis_client = get_redis_client()
            except Exception:
                try:
                    from .redis_session import get_redis_client
                    self._redis_client = get_redis_client()
                except Exception:
                    self._redis_client = None
        return self._redis_client

    def _make_key(self, user_id: str, window: str) -> str:
        """Create Redis key for rate limit counter."""
        # Sanitize user_id to prevent key injection
        safe_id = re.sub(r'[^a-zA-Z0-9@._-]', '_', user_id)
        return f"ratelimit:{safe_id}:{window}"

    def _incr_redis(self, key: str, ttl: int) -> int:
        """Atomic increment in Redis. Returns new count."""
        r = self._get_redis()
        if not r:
            return -1  # Signal fallback
        try:
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, ttl)  # Set TTL only on first INCR (idempotent)
            results = pipe.execute()
            return results[0]  # new count after INCR
        except Exception as e:
            logger.warning(f"⚠️ Redis rate-limit error: {e}")
            return -1

    def _get_redis_count(self, key: str) -> int:
        """Get current count from Redis."""
        r = self._get_redis()
        if not r:
            return 0
        try:
            val = r.get(key)
            return int(val) if val else 0
        except Exception:
            return 0

    def _get_redis_ttl(self, key: str) -> int:
        """Get remaining TTL of a Redis key."""
        r = self._get_redis()
        if not r:
            return 0
        try:
            ttl = r.ttl(key)
            return max(0, ttl) if ttl and ttl > 0 else 0
        except Exception:
            return 0

    def _incr_memory(self, key: str, ttl: int) -> int:
        """In-memory counter fallback."""
        now = time.time()
        with self._mem_lock:
            entry = self._mem_counters.get(key)
            if not entry or entry["expires"] <= now:
                self._mem_counters[key] = {"count": 1, "expires": now + ttl}
                return 1
            entry["count"] += 1
            return entry["count"]

    def _get_memory_count(self, key: str) -> int:
        """Get current in-memory count."""
        now = time.time()
        with self._mem_lock:
            entry = self._mem_counters.get(key)
            if not entry or entry["expires"] <= now:
                return 0
            return entry["count"]

    def _get_memory_ttl(self, key: str) -> int:
        """Get remaining TTL of an in-memory counter."""
        now = time.time()
        with self._mem_lock:
            entry = self._mem_counters.get(key)
            if not entry or entry["expires"] <= now:
                return 0
            return max(0, int(entry["expires"] - now))

    def check_and_increment(self, user_id: str, role: str = "user") -> Dict:
        """
        Check rate limit for user and increment counter.
        
        Returns dict:
          {
            "allowed": True/False,
            "role": "user",
            "daily_remaining": 45,
            "hourly_remaining": 18,
            "retry_after": 0,        # seconds until next window reset (if blocked)
            "message": ""            # Thai-friendly message (if blocked)
          }
        """
        quota = self.quotas.get(role, self.quotas["anonymous"])

        # Admin = unlimited
        if quota["daily"] == 0 and quota["hourly"] == 0:
            return {
                "allowed": True,
                "role": role,
                "daily_remaining": -1,   # -1 = unlimited
                "hourly_remaining": -1,
                "retry_after": 0,
                "message": "",
            }

        result = {"allowed": True, "role": role, "retry_after": 0, "message": ""}

        for window in ("hourly", "daily"):
            limit = quota[window]
            if limit <= 0:
                continue

            key = self._make_key(user_id, window)
            ttl = self.WINDOW_TTL[window]

            # Try Redis first
            count = self._incr_redis(key, ttl)
            if count == -1:
                # Redis unavailable → fallback to memory
                count = self._incr_memory(key, ttl)

            remaining = max(0, limit - count)
            result[f"{window}_remaining"] = remaining

            if count > limit:
                result["allowed"] = False
                # Get TTL for retry_after
                redis_ttl = self._get_redis_ttl(key)
                mem_ttl = self._get_memory_ttl(key)
                retry_after = redis_ttl or mem_ttl or ttl
                result["retry_after"] = max(result["retry_after"], retry_after)

                if window == "hourly":
                    minutes = retry_after // 60
                    result["message"] = (
                        f"⏳ คุณส่งข้อความเกินโควต้ารายชั่วโมงแล้วครับ ({limit} ข้อความ/ชม.)\n"
                        f"กรุณารอประมาณ {minutes} นาทีแล้วลองใหม่นะครับ 🙏"
                    )
                else:
                    result["message"] = (
                        f"⏳ คุณใช้งานครบโควต้าวันนี้แล้วครับ ({limit} ข้อความ/วัน)\n"
                        f"พรุ่งนี้กลับมาถามน้องดีโอได้อีกนะครับ 🌟"
                    )
                break  # No need to check further windows

        # Fill in missing remaining fields
        for window in ("hourly", "daily"):
            if f"{window}_remaining" not in result:
                limit = quota[window]
                if limit <= 0:
                    result[f"{window}_remaining"] = -1
                else:
                    key = self._make_key(user_id, window)
                    count = self._get_redis_count(key) or self._get_memory_count(key)
                    result[f"{window}_remaining"] = max(0, limit - count)

        return result

    def get_quota_info(self, user_id: str, role: str = "user") -> Dict:
        """
        Get quota status without incrementing.
        Used by /api/quota endpoint.
        """
        quota = self.quotas.get(role, self.quotas["anonymous"])

        if quota["daily"] == 0 and quota["hourly"] == 0:
            return {
                "role": role,
                "daily_limit": -1,
                "daily_used": 0,
                "daily_remaining": -1,
                "hourly_limit": -1,
                "hourly_used": 0,
                "hourly_remaining": -1,
            }

        info = {"role": role}
        for window in ("hourly", "daily"):
            limit = quota[window]
            if limit <= 0:
                info[f"{window}_limit"] = -1
                info[f"{window}_used"] = 0
                info[f"{window}_remaining"] = -1
                continue

            key = self._make_key(user_id, window)
            count = self._get_redis_count(key) or self._get_memory_count(key)
            info[f"{window}_limit"] = limit
            info[f"{window}_used"] = count
            info[f"{window}_remaining"] = max(0, limit - count)

        return info


# Global instances
input_sanitizer = InputSanitizer()
brute_force_guard = BruteForceProtection()
user_rate_limiter = UserRateLimiter()
