"""
Education Chatbot Module
Modular components for the DO-MOE Education Chatbot
"""

# Types and Enums
from .types import (
    QueryIntent,
    QueryLevel,
    ParsedQuery,
    SearchResult,
    LLMResponse,
    ChatMessage
)

# Constants
from .constants import (
    THAI_PROVINCES,
    PROVINCE_ALIASES,
    REGIONS,
    COLLECTIONS,
    AGENCY_ALIASES,
    COLLECTION_KEYWORDS,
    COLLECTION_SEARCH_ORDER,
    PRIMARY_COLLECTION
)

# Security
from .security import (
    InputSanitizer,
    input_sanitizer
)

# LLM
from .llm import MultiProviderLLM

# Cache
from .cache import (
    SemanticCache,
    HybridCache
)

# Query Parser
from .query_parser import (
    SmartQueryParser,
    LLMIntentClassifier,
    ResponseSynthesizer,
    INTENT_KEYWORDS
)

# Search Engines
from .search_engine import SearchEngine, route_to_collection
from .school_search import SchoolSearchEngine

# Aggregators
from .aggregators import ResultAggregator

# Formatters
from .formatters import ResponseFormatter

# Memory
from .memory import (
    ConversationMemory,
    session_memories,
    get_or_create_memory,
    clear_session_memory
)

# Main Chatbot Class
from .chatbot_core import EducationChatbot

__all__ = [
    # Types
    'QueryIntent',
    'QueryLevel', 
    'ParsedQuery',
    'SearchResult',
    'LLMResponse',
    'ChatMessage',
    # Constants
    'THAI_PROVINCES',
    'PROVINCE_ALIASES',
    'REGIONS',
    'COLLECTIONS',
    'AGENCY_ALIASES',
    'COLLECTION_KEYWORDS',
    'COLLECTION_SEARCH_ORDER',
    'PRIMARY_COLLECTION',
    'INTENT_KEYWORDS',
    # Security
    'InputSanitizer',
    'input_sanitizer',
    # LLM
    'MultiProviderLLM',
    # Cache
    'SemanticCache',
    'HybridCache',
    # Query Parser
    'SmartQueryParser',
    'LLMIntentClassifier',
    'ResponseSynthesizer',
    # Search Engines
    'SearchEngine',
    'route_to_collection',
    'SchoolSearchEngine',
    # Aggregators
    'ResultAggregator',
    # Formatters
    'ResponseFormatter',
    # Memory
    'ConversationMemory',
    'session_memories',
    'get_or_create_memory',
    'clear_session_memory',
    # Main Chatbot
    'EducationChatbot',
]

__version__ = '5.0.0'


