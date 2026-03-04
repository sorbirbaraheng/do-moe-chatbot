"""
🔧 ExecutorBase – Qdrant helpers and core infrastructure shared by all mixins.
"""

import logging
from typing import Dict, Any, List, Optional, Union

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition

from ..search.school_search import SchoolSearchEngine
from ..core.constants import (
    COLLECTION_NAMES,
    YEAR_COLLECTIONS,
    YEAR_ALIASES,
    AVAILABLE_YEARS,
)

logger = logging.getLogger(__name__)


class ExecutorBase:
    """Base class with Qdrant helpers and the execute() dispatcher."""

    def __init__(self, qdrant_client: QdrantClient, llm_provider=None):
        self.client = qdrant_client
        self.llm_provider = llm_provider

        # Use centralized collection names from constants
        self.collections = COLLECTION_NAMES.copy()

        # Active year for collection routing (set per-request in execute())
        self._active_year = None

        # Initialize specialized search engine
        self.search_engine = SchoolSearchEngine(self.client, llm_provider=llm_provider)

    # ------------------------------------------------------------------
    # Collection / year helpers
    # ------------------------------------------------------------------

    def _get_collection(self, key: str, year: str = None) -> str:
        """Get collection name based on year. Uses _active_year if year not specified."""
        y = year or self._active_year
        if y and y in YEAR_COLLECTIONS:
            return YEAR_COLLECTIONS[y].get(key, self.collections.get(key, ""))
        return self.collections.get(key, "")

    def _normalize_year(self, year: str = None) -> str:
        """Normalize year value (e.g. '67' -> '2567')"""
        if not year:
            return None
        year = str(year).strip()
        if year in YEAR_ALIASES:
            return YEAR_ALIASES[year]
        return year

    # ------------------------------------------------------------------
    # Qdrant primitives
    # ------------------------------------------------------------------

    def _build_filter(self, conditions: List[FieldCondition]) -> Optional[Filter]:
        """Build a Qdrant filter from conditions (supports nested Filter in list)."""
        if not conditions:
            return None

        must: List[Any] = []
        should: List[Any] = []
        must_not: List[Any] = []

        for cond in conditions:
            if isinstance(cond, Filter):
                # Flatten nested filter to avoid must=[Filter(...)] issues
                if cond.must:
                    must.extend(cond.must)
                if cond.should:
                    should.extend(cond.should)
                if cond.must_not:
                    must_not.extend(cond.must_not)
            else:
                must.append(cond)

        if not must and not should and not must_not:
            return None

        return Filter(
            must=must or None,
            should=should or None,
            must_not=must_not or None,
        )

    def _scroll_all(self, collection: str, scroll_filter: Optional[Filter],
                    limit: int = 1000, with_payload: Union[bool, List[str]] = True) -> List:
        """Scroll through all matching records"""
        all_results = []
        offset = None

        while len(all_results) < limit:
            response = self.client.scroll(
                collection_name=collection,
                scroll_filter=scroll_filter,
                limit=min(500, limit - len(all_results)),
                offset=offset,
                with_payload=with_payload
            )

            points = response[0]
            next_offset = response[1]

            all_results.extend(points)

            if next_offset is None or len(points) == 0:
                break
            offset = next_offset

        return all_results

    def _count_filtered(self, collection: str, count_filter: Optional[Filter]) -> int:
        """Count matching records without fetching them"""
        try:
            result = self.client.count(
                collection_name=collection,
                count_filter=count_filter,
                exact=True
            )
            return result.count
        except Exception as e:
            logger.warning(f"Count query failed: {e}, falling back to scroll count")
            # Fallback: do a scroll with high limit and count results
            return len(self._scroll_all(collection, count_filter, limit=10000))

    # ------------------------------------------------------------------
    # execute() dispatcher
    # ------------------------------------------------------------------

    def execute(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return structured data"""
        logger.info(f"🔧 Executing tool: {tool_name} with params: {params}")

        # Extract and normalize year for collection routing
        raw_year = params.get("year")
        self._active_year = self._normalize_year(raw_year)
        if raw_year and self._active_year not in AVAILABLE_YEARS:
            return {
                "tool": tool_name,
                "error": f"ไม่มีข้อมูลปี {self._active_year} ในระบบ",
                "available_years": AVAILABLE_YEARS,
            }
        if self._active_year:
            logger.info(f"📅 Year-based routing active: {self._active_year}")

        try:
            if tool_name == "search_schools":
                return self._search_schools(**params)
            elif tool_name == "count_teachers":
                return self._count_teachers(**params)
            elif tool_name == "count_students":
                return self._count_students(**params)
            elif tool_name == "count_schools":
                return self._count_schools(**params)
            elif tool_name == "get_ratio":
                return self._get_ratio(**params)
            elif tool_name == "compare":
                return self._compare(**params)
            elif tool_name == "ranking":
                return self._ranking(**params)
            elif tool_name == "list_schools":
                return self._list_schools(**params)
            elif tool_name == "filter_schools":
                return self._filter_schools(**params)
            # Phase 1: New tools
            elif tool_name == "search_education_areas":
                return self._search_education_areas(**params)
            elif tool_name == "get_education_area_info":
                return self._get_education_area_info(**params)
            elif tool_name == "get_school_full_details":
                if not params.get("school_name"):
                    return {
                        "tool": "get_school_full_details",
                        "error": "School name is required"
                    }
                return self._get_school_full_details(**params)
            elif tool_name == "get_province_summary":
                return self._get_province_summary(**params)
            elif tool_name == "get_national_summary":
                return self._get_national_summary(**params)
            # Phase 2: New tools
            elif tool_name == "count_by_system_type":
                return self._count_by_system_type(**params)
            elif tool_name == "analyze_gender_ratio":
                return self._analyze_gender_ratio(**params)
            elif tool_name == "get_grade_distribution":
                return self._get_grade_distribution(**params)
            elif tool_name == "find_best_ratio_schools":
                return self._find_best_ratio_schools(**params)
            # Phase 3: New tools
            elif tool_name == "analyze_teacher_distribution":
                return self._analyze_teacher_distribution(**params)
            elif tool_name == "ranking_by_agency":
                return self._ranking_by_agency(**params)
            elif tool_name == "ranking_subdistricts":
                return self._ranking_subdistricts(**params)
            elif tool_name == "get_district_summary":
                return self._get_district_summary(**params)
            elif tool_name == "compare_provinces":
                return self._compare_provinces(**params)
            elif tool_name == "compare_years":
                return self._compare_years(**params)
            elif tool_name == "find_nearby_schools":
                return self._find_nearby_schools(**params)
            elif tool_name == "general_chat":
                return {"type": "general_knowledge", "info": "Please answer this question using your general knowledge or RAG context."}
            elif tool_name == "advanced_school_search":
                return self._advanced_school_search(**params)
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            logger.error(f"❌ Tool execution error: {e}")
            return {"error": str(e)}
