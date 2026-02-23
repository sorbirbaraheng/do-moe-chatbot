"""
Handlers Module
Contains mixin classes for EducationChatbot handlers

📄 โมดูล handlers
📝 คำอธิบาย:
   รวม Mixin classes ที่แยกออกมาจาก chatbot_core.py
   เพื่อให้โค้ดอ่านง่ายและจัดการง่ายขึ้น
"""

from .llm_handlers import LLMHandlersMixin
from .stats_handlers import StatsHandlersMixin
from .intercept_handlers import InterceptHandlersMixin
from .school_handlers import SchoolHandlersMixin
from .search_handlers import SearchHandlersMixin

__all__ = [
    'LLMHandlersMixin',
    'StatsHandlersMixin',
    'InterceptHandlersMixin',
    'SchoolHandlersMixin',
    'SearchHandlersMixin',
]
