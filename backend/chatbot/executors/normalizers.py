"""
🔧 NormalizerMixin – Data normalization helpers (provinces, grades, agencies, etc.)
"""

import logging
from typing import Dict, Any, List, Optional

from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny

from ..core.constants import REGIONS

logger = logging.getLogger(__name__)


class NormalizerMixin:
    """Data normalization helpers used across all tool methods."""

    # ------------------------------------------------------------------
    # Thai numeral conversion
    # ------------------------------------------------------------------

    def _thai_to_arabic_numerals(self, text: str) -> str:
        """Convert Thai numerals to Arabic (๐๑๒๓๔๕๖๗๘๙ → 0123456789)"""
        if not text:
            return text
        thai_numerals = "๐๑๒๓๔๕๖๗๘๙"
        arabic_numerals = "0123456789"
        for thai, arabic in zip(thai_numerals, arabic_numerals):
            text = text.replace(thai, arabic)
        return text

    # ------------------------------------------------------------------
    # Province / Agency / Person-type / Grade / Region normalization
    # ------------------------------------------------------------------

    def _normalize_province(self, province: str) -> str:
        """Normalize province name with aliases"""
        if not province:
            return province
        province = province.replace("จ.", "").replace("จังหวัด", "").strip()

        # Bangkok aliases
        bangkok_aliases = ["กทม", "กทม.", "กรุงเทพ", "กรุงเทพฯ", "bkk"]
        if province.lower() in [a.lower() for a in bangkok_aliases]:
            return "กรุงเทพมหานคร"

        return province

    def _normalize_agency(self, agency: str) -> str:
        """Normalize agency abbreviations to full names"""
        if not agency:
            return agency

        agency_mapping = {
            "สพฐ": "สำนักงานคณะกรรมการการศึกษาขั้นพื้นฐาน",
            "สพฐ.": "สำนักงานคณะกรรมการการศึกษาขั้นพื้นฐาน",
            "สช": "สำนักงานคณะกรรมการส่งเสริมการศึกษาเอกชน",
            "สช.": "สำนักงานคณะกรรมการส่งเสริมการศึกษาเอกชน",
            "เอกชน": "สำนักงานคณะกรรมการส่งเสริมการศึกษาเอกชน",
            "อาชีวะ": "สำนักงานคณะกรรมการการอาชีวศึกษา",
            "สอศ": "สำนักงานคณะกรรมการการอาชีวศึกษา",
            "สอศ.": "สำนักงานคณะกรรมการการอาชีวศึกษา",
            "กทม": "กรุงเทพมหานคร",
            "กทม.": "กรุงเทพมหานคร",
            "ท้องถิ่น": "กรมส่งเสริมการปกครองท้องถิ่น",
            "อปท": "กรมส่งเสริมการปกครองท้องถิ่น",
            "อปท.": "กรมส่งเสริมการปกครองท้องถิ่น",
            "ตชด": "กองบัญชาการตำรวจตระเวนชายแดน",
            "ตชด.": "กองบัญชาการตำรวจตระเวนชายแดน",
        }

        agency_clean = agency.strip()
        return agency_mapping.get(agency_clean, agency)

    def _normalize_person_type(self, person_type: str) -> str:
        """Normalize person_type aliases to match Qdrant values"""
        if not person_type:
            return person_type

        person_type_mapping = {
            # ครูอัตราจ้าง variants
            "ครูอัตราจ้าง": "ลูกจ้างชั่วคราว",
            "อัตราจ้าง": "ลูกจ้างชั่วคราว",
            "ครูจ้าง": "ลูกจ้างชั่วคราว",
            # ข้าราชการครู variants
            "ครู": "ข้าราชการครู",
            "ข้าราชการ": "ข้าราชการครู",
            # พนักงานราชการ variants
            "พนง.ราชการ": "พนักงานราชการ",
            "พนง.": "พนักงานราชการ",
            # ลูกจ้าง variants
            "ลูกจ้าง": "ลูกจ้างชั่วคราว",
            "ลจ.": "ลูกจ้างชั่วคราว",
            "ลูกจ้างประจำ": "ลูกจ้างประจำ",  # Keep as-is
            # บุคลากร variants
            "บุคลากร": "บุคลากรทางการศึกษา",
        }

        pt_clean = person_type.strip()
        return person_type_mapping.get(pt_clean, pt_clean)

    def _normalize_grade(self, grade: str) -> str:
        """Normalize grade level name (e.g. ป.1 -> ประถมศึกษาปีที่ 1)"""
        if not grade:
            return grade

        grade = grade.strip()

        # Remove common prefixes
        for prefix in ["ชั้น", "ระดับชั้น", "ระดับ"]:
            if grade.startswith(prefix):
                grade = grade[len(prefix):].strip()

        mapping = {
            # อนุบาล
            "อ.1": "อนุบาล 1", "อ.2": "อนุบาล 2", "อ.3": "อนุบาล 3",
            "อนุบาล1": "อนุบาล 1", "อนุบาล2": "อนุบาล 2", "อนุบาล3": "อนุบาล 3",
            "อ1": "อนุบาล 1", "อ2": "อนุบาล 2", "อ3": "อนุบาล 3",
            # ประถมศึกษา
            "ป.1": "ประถมศึกษาปีที่ 1", "ป.2": "ประถมศึกษาปีที่ 2", "ป.3": "ประถมศึกษาปีที่ 3",
            "ป.4": "ประถมศึกษาปีที่ 4", "ป.5": "ประถมศึกษาปีที่ 5", "ป.6": "ประถมศึกษาปีที่ 6",
            "ป1": "ประถมศึกษาปีที่ 1", "ป2": "ประถมศึกษาปีที่ 2", "ป3": "ประถมศึกษาปีที่ 3",
            "ป4": "ประถมศึกษาปีที่ 4", "ป5": "ประถมศึกษาปีที่ 5", "ป6": "ประถมศึกษาปีที่ 6",
            # มัธยมศึกษา
            "ม.1": "มัธยมศึกษาปีที่ 1", "ม.2": "มัธยมศึกษาปีที่ 2", "ม.3": "มัธยมศึกษาปีที่ 3",
            "ม.4": "มัธยมศึกษาปีที่ 4", "ม.5": "มัธยมศึกษาปีที่ 5", "ม.6": "มัธยมศึกษาปีที่ 6",
            "ม1": "มัธยมศึกษาปีที่ 1", "ม2": "มัธยมศึกษาปีที่ 2", "ม3": "มัธยมศึกษาปีที่ 3",
            "ม4": "มัธยมศึกษาปีที่ 4", "ม5": "มัธยมศึกษาปีที่ 5", "ม6": "มัธยมศึกษาปีที่ 6",
            # อาชีวศึกษา - ปวช.
            "ปวช.1": "ประกาศนียบัตรวิชาชีพปีที่ 1", "ปวช.2": "ประกาศนียบัตรวิชาชีพปีที่ 2",
            "ปวช.3": "ประกาศนียบัตรวิชาชีพปีที่ 3",
            "ปวช1": "ประกาศนียบัตรวิชาชีพปีที่ 1", "ปวช2": "ประกาศนียบัตรวิชาชีพปีที่ 2",
            "ปวช3": "ประกาศนียบัตรวิชาชีพปีที่ 3",
            # อาชีวศึกษา - ปวส.
            "ปวส.1": "ประกาศนียบัตรวิชาชีพชั้นสูงชั้นปีที่ 1", "ปวส.2": "ประกาศนียบัตรวิชาชีพชั้นสูงชั้นปีที่ 2",
            "ปวส1": "ประกาศนียบัตรวิชาชีพชั้นสูงชั้นปีที่ 1", "ปวส2": "ประกาศนียบัตรวิชาชีพชั้นสูงชั้นปีที่ 2",
        }

        for k, v in mapping.items():
            if k in grade or grade == k:
                return v
        return grade

    def _normalize_region(self, region: str) -> Optional[str]:
        """Normalize region name (e.g. อีสาน -> ภาคตะวันออกเฉียงเหนือ)"""
        if not region:
            return None

        region = region.strip()
        if region in REGIONS:
            return region

        aliases = {
            "เหนือ": "ภาคเหนือ",
            "อีสาน": "ภาคตะวันออกเฉียงเหนือ",
            "ตะวันออกเฉียงเหนือ": "ภาคตะวันออกเฉียงเหนือ",
            "กลาง": "ภาคกลาง",
            "ตะวันออก": "ภาคตะวันออก",
            "ตะวันตก": "ภาคตะวันตก",
            "ใต้": "ภาคใต้",
        }

        if region in aliases:
            return aliases[region]

        for k, v in aliases.items():
            if k in region:
                return v

        return None

    # ------------------------------------------------------------------
    # Region aggregation
    # ------------------------------------------------------------------

    def _get_region_data(self, region: str, metric: str) -> Dict[str, Any]:
        """Aggregate data for a whole region"""
        provinces = REGIONS.get(region, [])
        if not provinces:
            return {"error": f"Region {region} not found"}

        logger.info(f"🌍 Aggregating data for region '{region}' ({len(provinces)} provinces)")

        province_filter = Filter(
            must=[
                FieldCondition(
                    key="metadata.province",
                    match=MatchAny(any=provinces)
                )
            ]
        )

        total = 0
        details = {}

        if metric == "schools":
            total = self._count_filtered(self._get_collection("schools"), province_filter)
            details = {"province_count": len(provinces)}

        elif metric == "students":
            schools_res = self._scroll_all(self._get_collection("schools"), province_filter, limit=50000,
                                           with_payload=["metadata.total_students"])
            total = sum(r.payload.get("metadata", {}).get("total_students", 0) for r in schools_res)
            details = {"source": "schools_aggregation"}

        elif metric == "teachers":
            schools_res = self._scroll_all(self._get_collection("schools"), province_filter, limit=50000,
                                           with_payload=["metadata.total_teachers"])
            total = sum(r.payload.get("metadata", {}).get("total_teachers", 0) for r in schools_res)
            details = {"source": "schools_aggregation"}

        elif metric == "ratio":
            students_res = self._scroll_all(self._get_collection("schools"), province_filter, limit=50000,
                                            with_payload=["metadata.total_students"])
            teachers_res = self._scroll_all(self._get_collection("schools"), province_filter, limit=50000,
                                            with_payload=["metadata.total_teachers"])

            total_s = sum(r.payload.get("metadata", {}).get("total_students", 0) for r in students_res)
            total_t = sum(r.payload.get("metadata", {}).get("total_teachers", 0) for r in teachers_res)

            details = {
                "total_students": total_s,
                "total_teachers": total_t,
                "source": "schools_aggregation"
            }
            total = round(total_s / total_t, 2) if total_t > 0 else 0

        return {
            "name": region,
            "type": "region",
            "total": total,
            "metric": metric,
            "details": details
        }

    # ------------------------------------------------------------------
    # Search query cleanup
    # ------------------------------------------------------------------

    def _clean_search_query(self, query: str) -> str:
        """Clean search query by removing common question words/particles"""
        if not query:
            return query

        remove_words = [
            "อยู่ที่ไหน", "ตั้งอยู่ที่ไหน", "อยู่ตรงไหน", "อยู่ไหน",
            "ไปทางไหน", "ไปยังไง", "แผนที่", "พิกัด", "ตำแหน่ง",
            "มีกี่แห่ง", "มีกี่โรงเรียน", "คืออะไร",
            "มีที่ไหนบ้าง", "ที่ไหนบ้าง", "มีที่ไหน", "ที่ไหน", "ที่ใด",
            "มีกี่ที่", "มีไหม", "บ้าง", "ทั้งหมด",
            "ครับ", "ค่ะ", "จ้ะ", "จ้า", "นะ", "นะคะ"
        ]

        clean = query
        for word in remove_words:
            clean = clean.replace(word, "")

        return clean.strip()
