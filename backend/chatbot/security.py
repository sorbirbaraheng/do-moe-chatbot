"""
Input Sanitization and Security for Education Chatbot
"""

import re
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class InputSanitizer:
    """Security layer for input validation and sanitization"""
    
    # Configuration
    MAX_LENGTH = 1000
    MIN_LENGTH = 1
    
    # Common prompt injection patterns
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
    ]
    
    def __init__(self):
        self.injection_regex = re.compile(
            '|'.join(self.INJECTION_PATTERNS), 
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
            logger.warning(f"🚨 Prompt injection attempt detected: {query[:50]}...")
            return "", "🛡️ ขออภัยครับ ข้อความนี้ไม่สามารถประมวลผลได้ กรุณาถามใหม่อีกครั้งครับ"
        
        # Basic sanitization: remove control characters
        query = ''.join(char for char in query if ord(char) >= 32 or char in '\n\t')
        
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


# Global sanitizer instance
input_sanitizer = InputSanitizer()
