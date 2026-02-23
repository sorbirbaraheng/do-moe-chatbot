"""
Result Aggregator for Education Chatbot
Handles aggregation of search results by location, region, and agency
"""

import logging
from typing import List
from collections import defaultdict

from ..core.types import SearchResult, QueryLevel
from ..core.constants import REGIONS

logger = logging.getLogger(__name__)


class ResultAggregator:
    """Aggregate and format search results"""
    
    def aggregate(self, results: List, level: QueryLevel, is_least: bool = False) -> SearchResult:
        """Aggregate results by location (Province/District/Subdistrict/Agency)"""
        aggregated = defaultdict(lambda: {'agencies': defaultdict(int), 'total': 0})
        
        for hit in results:
            meta = hit.payload.get('metadata', {})
            count = meta.get('count', 0)
            if not count: continue
            
            # Determine grouping key based on level
            name = ""
            if level == QueryLevel.PROVINCE:
                name = meta.get('province', '')
            elif level == QueryLevel.DISTRICT:
                prov = meta.get('province', '')
                dist = meta.get('district', '')
                name = f"{prov}|{dist}" if prov and dist else ""
            elif level == QueryLevel.SUBDISTRICT:
                prov = meta.get('province', '')
                dist = meta.get('district', '')
                sub = meta.get('subdistrict', '')
                name = f"{prov}|{dist}|{sub}" if all([prov, dist, sub]) else ""
            elif level == QueryLevel.AGENCY:
                name = meta.get('agency', '')
            
            if not name: continue
            
            aggregated[name]['total'] += count
            if meta.get('agency'):
                aggregated[name]['agencies'][meta.get('agency')] += count
        
        # Sort and return
        sorted_data = sorted(aggregated.items(), key=lambda x: x[1]['total'], reverse=not is_least)
        return SearchResult(data=sorted_data, count=len(sorted_data), is_least=is_least)

    def aggregate_by_region(self, results: List, is_least: bool = False) -> SearchResult:
        """Aggregate results by region using the REGIONS mapping"""
        # 1. Aggregate by province first
        province_totals = defaultdict(int)
        for hit in results:
            meta = hit.payload.get('metadata', {})
            count = meta.get('count', 0)
            province = meta.get('province')
            if province and count:
                province_totals[province] += count
        
        # 2. Group provinces into regions
        region_aggregated = defaultdict(lambda: {'total': 0})
        for region, provinces in REGIONS.items():
            if region == 'ภาคอีสาน': continue  # Alias
            for prov in provinces:
                if prov in province_totals:
                    region_aggregated[region]['total'] += province_totals[prov]
        
        sorted_data = sorted(region_aggregated.items(), key=lambda x: x[1]['total'], reverse=not is_least)
        return SearchResult(data=sorted_data, count=len(sorted_data), is_least=is_least)

    def aggregate_by_agency(self, results: List, province: str = None, region: str = None, is_least: bool = False) -> SearchResult:
        """Aggregate results by agency for a specific province or region"""
        agency_counts = defaultdict(lambda: {'total': 0})
        
        # Get list of provinces if filtering by region
        region_provinces = []
        if region and region != "each_region":
            region_provinces = REGIONS.get(region, [])
        
        for hit in results:
            meta = hit.payload.get('metadata', {})
            agency = meta.get('agency')
            count = meta.get('count', 0)
            hit_province = meta.get('province')
            
            # Filter by province if specified
            if province and hit_province != province:
                continue
            # Filter by region if specified
            if region_provinces and hit_province not in region_provinces:
                continue
                
            if agency and count:
                agency_counts[agency]['total'] += count
        
        sorted_data = sorted(agency_counts.items(), key=lambda x: x[1]['total'], reverse=not is_least)
        return SearchResult(data=sorted_data, count=len(sorted_data), is_least=is_least)
