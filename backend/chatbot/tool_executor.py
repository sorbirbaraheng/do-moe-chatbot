"""
🔧 Tool Executor
Executes tool calls by querying Qdrant and returning structured data.
"""

import logging
from typing import Dict, Any, List, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchText

logger = logging.getLogger(__name__)

class ToolExecutor:
    """
    Executes education chatbot tools against Qdrant database.
    Each tool returns structured data that LLM can use to generate responses.
    """
    
    def __init__(self, qdrant_client: QdrantClient):
        self.client = qdrant_client
        
        # V5 Collections mapping
        self.collections = {
            "schools": "edu_schools_v5",
            "teachers": "edu_teachers_v5",
            "students": "edu_students_v5",
            "ratios": "edu_ratios_v5",
            "areas": "edu_areas_v5",
        }
    
    def execute(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return structured data"""
        logger.info(f"🔧 Executing tool: {tool_name} with params: {params}")
        
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
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            logger.error(f"❌ Tool execution error: {e}")
            return {"error": str(e)}
    
    def _build_filter(self, conditions: List[FieldCondition]) -> Optional[Filter]:
        """Build a Qdrant filter from conditions"""
        if not conditions:
            return None
        return Filter(must=conditions)
    
    def _scroll_all(self, collection: str, scroll_filter: Optional[Filter], limit: int = 1000) -> List:
        """Scroll through all matching records"""
        all_results = []
        offset = None
        
        while len(all_results) < limit:
            response = self.client.scroll(
                collection_name=collection,
                scroll_filter=scroll_filter,
                limit=min(500, limit - len(all_results)),
                offset=offset,
                with_payload=True
            )
            
            points = response[0]
            next_offset = response[1]
            
            all_results.extend(points)
            
            if next_offset is None or len(points) == 0:
                break
            offset = next_offset
        
        return all_results
    
    # ============================================================
    # TOOL IMPLEMENTATIONS
    # ============================================================
    
    def _search_schools(self, school_name: str = None, province: str = None, 
                        district: str = None, agency: str = None, 
                        limit: int = 10) -> Dict[str, Any]:
        """Search for schools with various filters"""
        conditions = []
        
        if school_name:
            conditions.append(
                FieldCondition(key="metadata.school_name", match=MatchText(text=school_name))
            )
        if province:
            province = self._normalize_province(province)
            conditions.append(
                FieldCondition(key="metadata.province", match=MatchValue(value=province))
            )
        if district:
            conditions.append(
                FieldCondition(key="metadata.district", match=MatchText(text=district))
            )
        if agency:
            conditions.append(
                FieldCondition(key="metadata.agency", match=MatchText(text=agency))
            )
        
        scroll_filter = self._build_filter(conditions)
        results = self._scroll_all(self.collections["schools"], scroll_filter, limit=int(limit))
        
        schools = []
        for r in results:
            meta = r.payload.get("metadata", {})
            schools.append({
                "name": meta.get("school_name", "ไม่ระบุ"),
                "province": meta.get("province"),
                "district": meta.get("district"),
                "agency": meta.get("agency"),
                "address": meta.get("address"),
                "total_students": meta.get("total_students", 0),
                "total_teachers": meta.get("total_teachers", 0),
            })
        
        return {
            "tool": "search_schools",
            "total_found": len(schools),
            "schools": schools[:int(limit)]
        }
    
    def _count_teachers(self, school_name: str = None, province: str = None,
                        district: str = None, gender: str = None) -> Dict[str, Any]:
        """Count teachers with various filters"""
        conditions = []
        
        if school_name:
            conditions.append(
                FieldCondition(key="metadata.school_name", match=MatchText(text=school_name))
            )
        if province:
            province = self._normalize_province(province)
            conditions.append(
                FieldCondition(key="metadata.province", match=MatchValue(value=province))
            )
        if district:
            conditions.append(
                FieldCondition(key="metadata.district", match=MatchText(text=district))
            )
        if gender:
            conditions.append(
                FieldCondition(key="metadata.gender", match=MatchValue(value=gender))
            )
        
        scroll_filter = self._build_filter(conditions)
        results = self._scroll_all(self.collections["teachers"], scroll_filter)
        
        # Aggregate by school
        schools = {}
        total_count = 0
        total_male = 0
        total_female = 0
        
        for r in results:
            meta = r.payload.get("metadata", {})
            school = meta.get("school_name", "ไม่ระบุ")
            count = meta.get("count", 1)
            g = meta.get("gender", "-")
            
            if school not in schools:
                schools[school] = {"total": 0, "male": 0, "female": 0, "province": meta.get("province")}
            
            schools[school]["total"] += count
            total_count += count
            
            if g == "ชาย":
                schools[school]["male"] += count
                total_male += count
            elif g == "หญิง":
                schools[school]["female"] += count
                total_female += count
        
        return {
            "tool": "count_teachers",
            "query": {"school_name": school_name, "province": province, "gender": gender},
            "total_teachers": total_count,
            "by_gender": {"male": total_male, "female": total_female},
            "by_school": dict(list(schools.items())[:10]),
            "school_count": len(schools)
        }
    
    def _count_students(self, school_name: str = None, province: str = None,
                        district: str = None, grade: str = None, 
                        gender: str = None) -> Dict[str, Any]:
        """Count students with various filters"""
        conditions = []
        
        if school_name:
            conditions.append(
                FieldCondition(key="metadata.school_name", match=MatchText(text=school_name))
            )
        if province:
            province = self._normalize_province(province)
            conditions.append(
                FieldCondition(key="metadata.province", match=MatchValue(value=province))
            )
        if district:
            conditions.append(
                FieldCondition(key="metadata.district", match=MatchText(text=district))
            )
        if grade:
            grade = self._normalize_grade(grade)
            if grade:
                conditions.append(
                    FieldCondition(key="metadata.grade", match=MatchText(text=grade))
                )
        if gender:
            conditions.append(
                FieldCondition(key="metadata.gender", match=MatchValue(value=gender))
            )
        
        scroll_filter = self._build_filter(conditions)
        results = self._scroll_all(self.collections["students"], scroll_filter)
        
        # Aggregate
        schools = {}
        total_count = 0
        total_male = 0
        total_female = 0
        
        for r in results:
            meta = r.payload.get("metadata", {})
            school = meta.get("school_name", "ไม่ระบุ")
            count = meta.get("count", 1)
            g = meta.get("gender", "-")
            
            if school not in schools:
                schools[school] = {"total": 0, "male": 0, "female": 0, "province": meta.get("province")}
            
            schools[school]["total"] += count
            total_count += count
            
            if g == "ชาย":
                schools[school]["male"] += count
                total_male += count
            elif g == "หญิง":
                schools[school]["female"] += count
                total_female += count
        
        return {
            "tool": "count_students",
            "query": {"school_name": school_name, "province": province, "grade": grade, "gender": gender},
            "total_students": total_count,
            "by_gender": {"male": total_male, "female": total_female},
            "by_school": dict(list(schools.items())[:10]),
            "school_count": len(schools)
        }
    
    def _count_schools(self, province: str = None, district: str = None,
                       agency: str = None) -> Dict[str, Any]:
        """Count schools in an area"""
        conditions = []
        
        if province:
            province = self._normalize_province(province)
            conditions.append(
                FieldCondition(key="metadata.province", match=MatchValue(value=province))
            )
        if district:
            conditions.append(
                FieldCondition(key="metadata.district", match=MatchText(text=district))
            )
        if agency:
            conditions.append(
                FieldCondition(key="metadata.agency", match=MatchText(text=agency))
            )
        
        scroll_filter = self._build_filter(conditions)
        # Increase limit to 10000 to handle large provinces like Bangkok
        results = self._scroll_all(self.collections["schools"], scroll_filter, limit=10000)
        
        # Group by agency
        agencies = {}
        for r in results:
            meta = r.payload.get("metadata", {})
            ag = meta.get("agency", "ไม่ระบุ")
            agencies[ag] = agencies.get(ag, 0) + 1
        
        return {
            "tool": "count_schools",
            "query": {"province": province, "district": district, "agency": agency},
            "total_schools": len(results),
            "by_agency": agencies
        }
    
    def _get_ratio(self, school_name: str = None, province: str = None) -> Dict[str, Any]:
        """Get student-teacher ratio"""
        conditions = []
        
        if school_name:
            conditions.append(
                FieldCondition(key="metadata.school_name", match=MatchText(text=school_name))
            )
        if province:
            province = self._normalize_province(province)
            conditions.append(
                FieldCondition(key="metadata.province", match=MatchValue(value=province))
            )
        
        scroll_filter = self._build_filter(conditions)
        results = self._scroll_all(self.collections["ratios"], scroll_filter, limit=50)
        
        ratios = []
        for r in results:
            meta = r.payload.get("metadata", {})
            ratios.append({
                "school_name": meta.get("school_name"),
                "ratio": meta.get("ratio", 0),
                "students": meta.get("total_students", 0),
                "teachers": meta.get("total_teachers", 0),
                "province": meta.get("province"),
            })
        
        return {
            "tool": "get_ratio",
            "query": {"school_name": school_name, "province": province},
            "ratios": ratios[:10]
        }
    
    def _compare(self, entity1: str, entity2: str, metric: str) -> Dict[str, Any]:
        """Compare two entities (schools or provinces)"""
        result1 = None
        result2 = None
        
        if metric == "students":
            result1 = self._count_students(school_name=entity1)
            result2 = self._count_students(school_name=entity2)
            # If no results, try as province
            if result1["total_students"] == 0:
                result1 = self._count_students(province=entity1)
            if result2["total_students"] == 0:
                result2 = self._count_students(province=entity2)
            
        elif metric == "teachers":
            result1 = self._count_teachers(school_name=entity1)
            result2 = self._count_teachers(school_name=entity2)
            if result1["total_teachers"] == 0:
                result1 = self._count_teachers(province=entity1)
            if result2["total_teachers"] == 0:
                result2 = self._count_teachers(province=entity2)
                
        elif metric == "schools":
            result1 = self._count_schools(province=entity1)
            result2 = self._count_schools(province=entity2)
            
        elif metric == "ratio":
            result1 = self._get_ratio(school_name=entity1)
            result2 = self._get_ratio(school_name=entity2)
        
        return {
            "tool": "compare",
            "entity1": {"name": entity1, "data": result1},
            "entity2": {"name": entity2, "data": result2},
            "metric": metric
        }
    
    def _ranking(self, metric: str, order: str, scope: str = "school",
                 province: str = None, limit: int = 5) -> Dict[str, Any]:
        """Get ranking of schools or provinces by a metric"""
        limit = int(limit)
        
        if metric == "students":
            data = self._count_students(province=province)
            items = [(k, v["total"]) for k, v in data.get("by_school", {}).items()]
        elif metric == "teachers":
            data = self._count_teachers(province=province)
            items = [(k, v["total"]) for k, v in data.get("by_school", {}).items()]
        else:
            return {"error": f"Ranking metric '{metric}' not supported"}
        
        # Sort based on order
        reverse = order == "most"
        items.sort(key=lambda x: x[1], reverse=reverse)
        
        ranking = []
        for i, (name, count) in enumerate(items[:limit], 1):
            ranking.append({"rank": i, "name": name, "count": count})
        
        return {
            "tool": "ranking",
            "metric": metric,
            "order": order,
            "scope": scope,
            "province": province,
            "ranking": ranking
        }
    
    def _list_schools(self, province: str = None, district: str = None,
                      agency: str = None, limit: int = 10) -> Dict[str, Any]:
        """List schools in an area"""
        return self._search_schools(province=province, district=district, 
                                    agency=agency, limit=limit)
    
    # ============================================================
    # HELPER METHODS
    # ============================================================
    
    def _normalize_province(self, province: str) -> str:
        """Normalize province name"""
        if not province:
            return province
            
        # Bangkok variations
        bkk_names = ['กรุงเทพ', 'กทม', 'บางกอก', 'กรุงเทพฯ']
        for name in bkk_names:
            if name in province:
                return 'กรุงเทพมหานคร'
        
        return province
    
    def _normalize_grade(self, grade: str) -> str:
        """Normalize grade level"""
        if not grade:
            return None
            
        # Common mappings
        mappings = {
            'ป.1': 'ประถมศึกษาปีที่ 1', 'ป.2': 'ประถมศึกษาปีที่ 2',
            'ป.3': 'ประถมศึกษาปีที่ 3', 'ป.4': 'ประถมศึกษาปีที่ 4',
            'ป.5': 'ประถมศึกษาปีที่ 5', 'ป.6': 'ประถมศึกษาปีที่ 6',
            'ม.1': 'มัธยมศึกษาปีที่ 1', 'ม.2': 'มัธยมศึกษาปีที่ 2',
            'ม.3': 'มัธยมศึกษาปีที่ 3', 'ม.4': 'มัธยมศึกษาปีที่ 4',
            'ม.5': 'มัธยมศึกษาปีที่ 5', 'ม.6': 'มัธยมศึกษาปีที่ 6',
        }
        
        return mappings.get(grade, grade)
