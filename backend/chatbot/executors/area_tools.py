"""
🔧 AreaToolsMixin – Education-area search and info tools.
"""

import logging
from typing import Dict, Any

from qdrant_client import models
from qdrant_client.models import FieldCondition, MatchValue, MatchText

logger = logging.getLogger(__name__)


class AreaToolsMixin:
    """Education-area related tool implementations."""

    def _search_education_areas(self, area_name: str = None, province: str = None,
                                 district: str = None) -> Dict[str, Any]:
        """Search for education areas (สพป./สพม.) with their covered districts"""
        try:
            results = self._scroll_all(self._get_collection("areas"), None, limit=500)
        except Exception as e:
            logger.warning(f"⚠️ Could not query education areas collection: {e}")
            return {
                "tool": "search_education_areas",
                "query": {"area_name": area_name, "province": province, "district": district},
                "total_found": 0,
                "areas": [],
                "note": "Education areas collection not available"
            }

        areas = []
        for r in results:
            meta = r.payload.get("metadata", {})
            area_name_val = meta.get("area_name", "")

            if not area_name_val or area_name_val == "nan" or str(area_name_val).lower() == "nan":
                continue

            if area_name:
                search_name = area_name.lower().replace('สพด.', 'สพป.').replace('สพด', 'สพป')
                stored_lower = area_name_val.lower()

                key_parts = []
                if 'เขต' in search_name:
                    parts = search_name.replace('สพป.', '').replace('สพม.', '').split()
                    for part in parts:
                        if part and len(part) > 1:
                            key_parts.append(part)
                else:
                    key_parts = [search_name]

                match = all(part in stored_lower for part in key_parts if part not in ['สพป', 'สพม'])
                if not match and search_name not in stored_lower:
                    continue

            if province:
                province_normalized = self._normalize_province(province)
                provinces_list = meta.get("provinces", [])
                text_field = r.payload.get("text", "")
                province_match = any(province_normalized in str(p) for p in provinces_list)
                text_match = province_normalized in text_field
                if not (province_match or text_match):
                    continue

            if district:
                districts_list = meta.get("districts_list", [])
                text_field = r.payload.get("text", "")
                district_match = any(district in str(d) for d in districts_list)
                text_match = district in text_field
                if not (district_match or text_match):
                    continue

            areas.append({
                "area_name": area_name_val,
                "provinces": meta.get("provinces", []),
                "districts_count": meta.get("districts_count", 0),
                "districts_list": meta.get("districts_list", []),
                "school_count": meta.get("school_count", 0),
            })

        return {
            "tool": "search_education_areas",
            "query": {"area_name": area_name, "province": province, "district": district},
            "total_found": len(areas),
            "areas": areas
        }

    def _get_education_area_info(self, area_name: str, **kwargs) -> Dict[str, Any]:
        """Get information about an education service area including covered districts"""
        if not area_name:
            return {"error": "กรุณาระบุชื่อเขตพื้นที่การศึกษา เช่น สพป.เชียงใหม่ เขต 1"}

        normalized = area_name.strip()
        normalized = normalized.replace("สพป ", "สพป.").replace("สพม ", "สพม.")
        normalized = normalized.replace("สพป.", "สพป. ").replace("สพม.", "สพม. ")
        normalized = " ".join(normalized.split())

        logger.info(f"🏫 Searching education area info: {normalized}")

        try:
            results = self.client.scroll(
                collection_name=self._get_collection("schools"),
                limit=2000,
                with_payload=True,
                scroll_filter=models.Filter(
                    should=[
                        models.FieldCondition(
                            key="metadata.area_name",
                            match=models.MatchValue(value=normalized)
                        ),
                        models.FieldCondition(
                            key="metadata.area_name",
                            match=models.MatchValue(value=area_name)
                        ),
                    ]
                )
            )

            schools = results[0]

            if not schools:
                logger.info(f"   No exact match, trying partial search...")
                all_results = self.client.scroll(
                    collection_name=self._get_collection("schools"),
                    limit=5000,
                    with_payload=True
                )

                keyword = area_name.replace("สพป.", "").replace("สพม.", "").strip()
                schools = [
                    s for s in all_results[0]
                    if keyword.lower() in (s.payload.get("metadata", {}).get("area_name", "") or "").lower()
                ]

            if not schools:
                return {
                    "tool": "get_education_area_info",
                    "error": f"ไม่พบข้อมูลเขตพื้นที่ '{area_name}'"
                }

            districts = {}
            province_set = set()
            for s in schools:
                meta = s.payload.get("metadata", s.payload)
                district = meta.get("district", "ไม่ระบุ")
                province_set.add(meta.get("province", ""))
                districts[district] = districts.get(district, 0) + 1

            sorted_districts = sorted(districts.items(), key=lambda x: -x[1])

            actual_area = schools[0].payload.get("metadata", {}).get("area_name", area_name)
            province = list(province_set)[0] if province_set else None

            logger.info(f"   Found {len(schools)} schools in {len(districts)} districts")

            return {
                "tool": "get_education_area_info",
                "area_name": actual_area,
                "province": province,
                "total_schools": len(schools),
                "total_districts": len(districts),
                "districts": [d[0] for d in sorted_districts],
                "schools_by_district": dict(sorted_districts),
            }

        except Exception as e:
            logger.error(f"❌ Error getting education area info: {e}")
            return {"tool": "get_education_area_info", "error": str(e)}
