"""WidgetMixin - UI widget injection (map, chart) + proactive suggestions."""
import json
import logging
from typing import Dict, Any, List
logger = logging.getLogger(__name__)

class WidgetMixin:

    def _generate_map_json(self, schools: List[Dict]) -> str:
        """Helper to generate Map Widget JSON for single or multiple schools"""
        import json
        
        if not schools:
            return ""
            
        # Primary marker (use the first one as center/main)
        primary = schools[0]
        
        # Build Address
        parts = []
        if primary.get("subdistrict"): parts.append(str(primary.get("subdistrict")))
        if primary.get("district"): parts.append(str(primary.get("district")))
        if primary.get("province"): parts.append(str(primary.get("province")))
        if primary.get("postcode"): parts.append(str(primary.get("postcode")))
        address = " ".join(parts)

        data = {
            "latitude": float(primary.get("lat", 0)),
            "longitude": float(primary.get("lon", 0)),
            "schoolName": primary.get("name", ""),
            "address": address
        }

        # If multiple schools, add 'markers' field
        if len(schools) > 1:
            markers = []
            for s in schools:
                markers.append({
                    "lat": float(s.get("lat", 0)),
                    "lng": float(s.get("lon", 0)),
                    "title": s.get("name", "")
                })
            data["markers"] = markers
            
        return json.dumps(data, ensure_ascii=False)
    def _inject_widgets(self, text: str, results: List[Dict], question: str = "") -> str:
        """Inject UI widgets (Map, Chart, etc.) based on data"""
        try:
            import json
            
            # Check for explicit user request for a chart
            chart_keywords = ['กราฟ', 'แผนภูมิ', 'chart', 'graph', 'visual', 'trend', 'แนวโน้ม']
            is_explicit_chart_req = any(k in question.lower() for k in chart_keywords)

            # Loop through results to find widget opportunities
            for res in results:
                tool = res.get("tool")
                
                # ============================================
                # LLM-DRIVEN FORMAT SELECTION (NEW APPROACH)
                # ============================================
                # Map and Chart widgets are now handled by LLM via RESPONSE_GENERATION_PROMPT
                # The LLM decides whether to include <map> or <chart> based on context
                # Keeping this code as fallback (commented out) if LLM fails to include widgets
                
                # FALLBACK: Map Widget Injection (only if LLM didn't include one)
                if tool == "get_school_full_details" and res.get("lat") and res.get("lon"):
                    # Only inject if LLM didn't already include a map
                    if "<map>" not in text:
                        school = {
                            "name": res.get("school_name", "School"),
                            "lat": res.get("lat"),
                            "lon": res.get("lon"),
                            "subdistrict": res.get("subdistrict"),
                            "district": res.get("district"),
                            "province": res.get("province"),
                            "postcode": res.get("postcode")
                        }
                        map_json = self._generate_map_json([school])
                        text += f"\n\n<map>{map_json}</map>"
                        logger.info("📍 Map widget added as fallback (LLM didn't include)")
                
                # FALLBACK: Chart Widget Injection (only if LLM didn't include one)
                # Ranking Chart - fallback for ranking tool
                if tool == "ranking" and res.get("ranking") and "<chart>" not in text:
                    ranking_data = res.get("ranking", [])
                    chart_data = []
                    for item in ranking_data[:10]: # Top 10
                         name = item.get("name", "")
                         if '|' in name: # Clean up name if pipeline format
                             name = name.split('|')[1].strip() if len(name.split('|')) > 1 else name
                         value = item.get("count", 0)
                         chart_data.append({"name": name, "value": value})
                    
                    if chart_data:
                        title = "น้อยที่สุด" if res.get("order") == "least" else "มากที่สุด"
                        chart_json = json.dumps({
                            "type": "bar",
                            "data": chart_data,
                            "title": f"สถิติ{title}"
                        }, ensure_ascii=False)
                        text += f"\n\n<chart>{chart_json}</chart>"
                        logger.info("📊 Chart widget added as fallback (LLM didn't include)")
                        
                # Comparison Chart (Region/Province/School) - ALWAYS SHOW
                elif tool == "compare":
                    e1 = res.get("entity1", {})
                    e2 = res.get("entity2", {})
                    metric = res.get("metric", "value")
                    
                    name1 = e1.get("name", "Entity 1")
                    name2 = e2.get("name", "Entity 2")
                    
                    # Extract total value safely - handle None data
                    data1 = e1.get("data") or {}
                    data2 = e2.get("data") or {}
                    
                    # Try multiple possible keys for the value
                    val1 = data1.get("total_schools", 0) or data1.get("total_students", 0) or data1.get("total_teachers", 0) or data1.get("total", 0) or data1.get("count", 0)
                    val2 = data2.get("total_schools", 0) or data2.get("total_students", 0) or data2.get("total_teachers", 0) or data2.get("total", 0) or data2.get("count", 0)
                    
                    chart_data = [
                        {"name": name1, "value": val1},
                        {"name": name2, "value": val2}
                    ]
                    
                    if val1 > 0 or val2 > 0:
                        chart_title = f"เปรียบเทียบ{metric}"
                        chart_json = json.dumps({
                            "type": "bar",
                            "data": chart_data,
                            "title": chart_title
                        }, ensure_ascii=False)
                        if "<chart>" not in text:
                            text += f"\n\n<chart>{chart_json}</chart>"
                            logger.info(f"📊 Comparison chart injected: {name1}={val1}, {name2}={val2}")
                    if is_explicit_chart_req:
                        by_gender = res.get("by_gender", {})
                        male = by_gender.get('male', 0)
                        female = by_gender.get('female', 0)
                        
                        if male > 0 or female > 0:
                            chart_data = [
                                {"name": "ชาย", "value": male},
                                {"name": "หญิง", "value": female}
                            ]
                            chart_json = json.dumps({
                               "type": "pie",
                               "data": chart_data,
                               "title": "สัดส่วนนักเรียนแยกตามเพศ"
                           }, ensure_ascii=False)
                            if "<chart>" not in text:
                               text += f"\n\n<chart>{chart_json}</chart>"
                            
        except Exception as e:
            logger.error(f"❌ Failed to inject widgets: {e}")
            
        return text
    def _get_proactive_suggestions(self, tool_calls: List[Dict], results: List[Dict]) -> List[str]:
        """
        Generate proactive follow-up suggestions based on tool results.
        Returns a list of suggestion strings for frontend to render as clickable chips.
        """
        suggestions = []
        
        for tool_call, result in zip(tool_calls, results):
            name = tool_call.get("name")
            params = tool_call.get("params", {})
            
            # Scenario 1: User asked for school details
            if name == "get_school_full_details" or (name == "search_schools" and result.get("total_count", 0) == 1):
                school_name = params.get("school_name") or "โรงเรียนนี้"
                suggestions.append(f"เปรียบเทียบจำนวนนักเรียนของ {school_name} กับโรงเรียนใกล้เคียง")
                suggestions.append(f"ดูอัตราส่วนครูต่อนักเรียนของ {school_name}")
                suggestions.append(f"ดูจำนวนนักเรียนแยกตามระดับชั้น (ชาย/หญิง)")

            # Scenario 2: User asked for student count (School level)
            elif name == "count_students" and params.get("school_name"):
                suggestions.append("ดูจำนวนครูเพื่อหาอัตราส่วน")
                suggestions.append("ดูข้อมูลที่ตั้งและรายละเอียดโรงเรียนเพิ่มเติม")

            # Scenario 3: User asked for student count (Province level)
            elif name == "count_students" and params.get("province"):
                prov = params.get("province")
                suggestions.append(f"จัดอันดับ 5 โรงเรียนที่มีนักเรียนมากที่สุดใน{prov}")
                suggestions.append(f"ดูจำนวนโรงเรียนทั้งหมดใน{prov}")
            
            # Scenario 4: Ranking
            elif name == "ranking":
                suggestions.append("ดูรายละเอียดของโรงเรียนอันดับ 1")
                suggestions.append("เปรียบเทียบโรงเรียนอันดับ 1 กับอันดับ 2")

            # Scenario 5: Province summary
            elif name == "get_province_summary":
                prov = params.get("province") or "จังหวัดนี้"
                suggestions.append(f"จัดอันดับโรงเรียนที่มีนักเรียนมากที่สุดใน{prov}")
                suggestions.append(f"อัตราส่วนครูต่อนักเรียนของ{prov}")
                suggestions.append(f"แยกจำนวนนักเรียนตามอำเภอใน{prov}")

            # Scenario 6: Teacher count
            elif name == "count_teachers":
                if params.get("school_name"):
                    suggestions.append(f"ดูจำนวนนักเรียนของ {params['school_name']}")
                    suggestions.append(f"ดูอัตราส่วนครูต่อนักเรียนของ {params['school_name']}")
                elif params.get("province"):
                    suggestions.append(f"แยกตามประเภทบุคลากรใน{params['province']}")
                    suggestions.append(f"จัดอันดับโรงเรียนที่มีครูมากที่สุดใน{params['province']}")

            # Scenario 7: Count schools
            elif name == "count_schools":
                prov = params.get("province")
                if prov:
                    suggestions.append(f"จัดอันดับโรงเรียนที่มีนักเรียนมากที่สุดใน{prov}")
                    suggestions.append(f"อัตราส่วนครูต่อนักเรียนของ{prov}")
                    suggestions.append(f"จำนวนครูทั้งหมดใน{prov}")

            # Scenario 8: Search/List schools (multi-result)
            elif name in ("search_schools", "list_schools", "advanced_school_search"):
                prov = params.get("province")
                if prov:
                    suggestions.append(f"จัดอันดับโรงเรียนที่มีนักเรียนมากที่สุดใน{prov}")
                    suggestions.append(f"จำนวนนักเรียนทั้งหมดใน{prov}")
                    suggestions.append(f"อัตราส่วนครูต่อนักเรียนของ{prov}")
                else:
                    suggestions.append("ดูรายละเอียดเพิ่มเติมของโรงเรียนลำดับแรก")
                    suggestions.append("จัดอันดับโรงเรียนที่มีนักเรียนมากที่สุด")

            # Scenario 9: Get ratio
            elif name == "get_ratio":
                school_name = params.get("school_name")
                prov = params.get("province")
                if school_name:
                    suggestions.append(f"ดูจำนวนนักเรียนแยกตามระดับชั้นของ {school_name}")
                    suggestions.append(f"ดูรายละเอียดเพิ่มเติมของ {school_name}")
                elif prov:
                    suggestions.append(f"จัดอันดับโรงเรียนที่มีอัตราส่วนครูต่อนักเรียนดีที่สุดใน{prov}")
                    suggestions.append(f"จำนวนครูทั้งหมดใน{prov}")

            # Scenario 10: Grade distribution
            elif name == "get_grade_distribution":
                school_name = params.get("school_name")
                if school_name:
                    suggestions.append(f"ดูอัตราส่วนครูต่อนักเรียนของ {school_name}")
                    suggestions.append(f"เปรียบเทียบ {school_name} กับโรงเรียนใกล้เคียง")

        if not suggestions:
            return []
            
        return suggestions[:3]
