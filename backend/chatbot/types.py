"""
Types and Enums for Education Chatbot
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Any, Dict, Tuple


class QueryIntent(Enum):
    """Types of user queries"""
    COUNT = "count"
    RANKING_MOST = "ranking_most"
    RANKING_LEAST = "ranking_least"
    COMPARE = "compare"
    SEARCH = "search"
    LIST = "list"
    SCHOOL_SEARCH = "school_search"
    SCHOOL_LIST = "school_list"
    SCHOOL_DETAIL = "school_detail"
    SCHOOL_COUNT = "school_count"
    LOAD_MORE = "load_more"  # Pagination - load more results
    # Threshold-based filtering (e.g., "มากกว่า 50 แห่ง", "น้อยกว่า 100 โรง")
    FILTER_LESS_THAN = "filter_less_than"
    FILTER_GREATER_THAN = "filter_greater_than"
    FILTER_EQUALS = "filter_equals"
    UNKNOWN = "unknown"


class QueryLevel(Enum):
    """Geographic level of query"""
    REGION = "region"
    PROVINCE = "province"
    DISTRICT = "district"
    SUBDISTRICT = "subdistrict"
    AGENCY = "agency"


@dataclass
class ParsedQuery:
    """Parsed query with extracted entities"""
    intent: QueryIntent
    level: QueryLevel = QueryLevel.PROVINCE
    province: Optional[str] = None
    district: Optional[str] = None
    subdistrict: Optional[str] = None
    agency: Optional[str] = None
    region: Optional[str] = None
    compare_targets: Optional[List[str]] = None
    raw_query: str = ""
    school_name: Optional[str] = None
    original_query: str = ""
    normalized_query: str = ""
    confidence: float = 0.0
    # Threshold filtering fields (e.g., "น้อยกว่า 50 แห่ง")
    threshold: Optional[int] = None
    threshold_operator: Optional[str] = None  # "<", ">", "="


@dataclass
class SearchResult:
    """Search result container"""
    data: List[Tuple[str, Dict]] = field(default_factory=list)
    count: int = 0
    is_least: bool = False
    source: str = ""
    search_time_ms: float = 0


@dataclass
class LLMResponse:
    """LLM Response wrapper with provider info"""
    text: str
    provider: str = "unknown"


@dataclass
class ChatMessage:
    """Chat message structure"""
    role: str  # "user" or "assistant"
    content: str
