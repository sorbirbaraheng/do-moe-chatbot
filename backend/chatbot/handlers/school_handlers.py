"""SchoolHandlersMixin - School query/count/list/search/detail handlers."""
import re
import logging
from typing import Dict, List, Optional, Any
from ..core.types import ParsedQuery, QueryIntent, QueryLevel, SearchResult
from ..search.query_parser import SmartQueryParser, ResponseSynthesizer
from ..search.school_search import SchoolSearchEngine
logger = logging.getLogger(__name__)

class SchoolHandlersMixin:
    """School-related query handlers extracted from chatbot_core.py."""


    def _handle_school_query(self, parsed: ParsedQuery, message: str, history: List) -> Optional[str]:
        """Handle school-related queries"""
        school_engine = SchoolSearchEngine(self.qdrant_client, llm_provider=self.model)
        synthesizer = ResponseSynthesizer()
        response_text = ""
        
        if parsed.intent == QueryIntent.SCHOOL_DETAIL:
            school_name = parsed.school_name
            
            if not school_name:
                query_lower = message.lower()
                phrases_to_remove = [
                    'ข้อมูลโรงเรียน', 'รายละเอียดโรงเรียน', 'เบอร์โทรโรงเรียน',
                    'ที่อยู่โรงเรียน', 'ติดต่อโรงเรียน', 'โรงเรียน', 'ร.ร.', 'รร.',
                    'อยู่ที่ไหน', 'อยู่ตรงไหน', 'อยู่ไหน', 'ตั้งอยู่ที่ไหน',
                    'ขอข้อมูล', 'ขอรายละเอียด', 'ขอดู', 'หา', 'ค้นหา',
                    'ครับ', 'ค่ะ', 'หน่อย', 'ได้ไหม', 'มั้ย', 'บ้าง',
                    'ที่ตั้ง', 'ที่อยู่', 'ของ', 'ที่', 'ขอ',
                    # Additional phrases to remove
                    'รายละเอียด', 'ข้อมูล', 'เบอร์โทร', 'เบอร์', 'โทรศัพท์',
                    'ติดต่อ', 'สอบถาม', 'ดู', 'แสดง', 'บอก', 'ช่วย'
                ]
                school_name = query_lower
                for phrase in phrases_to_remove:
                    school_name = school_name.replace(phrase, '')
                school_name = ' '.join(school_name.split()).strip()
            
            if school_name:
                details = school_engine.get_school_details(school_name)
                if details:
                    data = {
                        "query_type": "school_detail",
                        "school": {
                            "name": details.get('school_name'),
                            "address": {
                                "subdistrict": details.get('subdistrict'),
                                "district": details.get('district'),
                                "province": details.get('province'),
                                "postcode": details.get('postcode')
                            },
                            "agency": details.get('agency'),
                            "phone": details.get('phone1') or details.get('phone2'),
                            "school_code": details.get('school_code'),
                        }
                    }
                    
                    llm_response = synthesizer.synthesize("SCHOOL_DETAIL", data, message)
                    
                    if llm_response:
                        response_text = llm_response
                    else:
                        # Fallback template with น้องดีโอ personality
                        address = f"ต.{details.get('subdistrict', '-')} อ.{details.get('district', '-')} จ.{details.get('province', '-')}"
                        response_text = f"📍 **ข้อมูลโรงเรียน{details.get('school_name')}**\n\n"
                        response_text += f"สวัสดีครับพี่! น้องดีโอหาข้อมูลมาให้แล้วนะครับ 😊\n\n"
                        response_text += f"🏫 **ชื่อ**: {details.get('school_name')}\n"
                        response_text += f"📌 **ที่ตั้ง**: {address}\n"
                        response_text += f"🏛️ **สังกัด**: {details.get('agency')}\n"
                        if details.get('phone1'):
                            response_text += f"📞 **โทรศัพท์**: {details.get('phone1')}\n"
                    
                    # Add map if coordinates available
                    lat = details.get('latitude')
                    lng = details.get('longitude')
                    if lat and lng:
                        try:
                            address = f"ต.{details.get('subdistrict', '-')} อ.{details.get('district', '-')} จ.{details.get('province', '-')}"
                            map_json = json.dumps({
                                "latitude": float(lat),
                                "longitude": float(lng), 
                                "schoolName": details.get('school_name', school_name),
                                "address": address
                            }, ensure_ascii=False)
                            response_text += f"\n<map>{map_json}</map>"
                        except:
                            pass
                    
                    response_text += f"\n\n💡 **คำถามที่น่าสนใจ**\n"
                    response_text += f"• รายชื่อโรงเรียนในอำเภอ{details.get('district', '')}?\n"
                    response_text += f"• จังหวัด{details.get('province', '')}มีโรงเรียนกี่แห่ง?\n"
                else:
                    response_text = f"❌ ไม่พบข้อมูลโรงเรียน \"{school_name}\" ในฐานข้อมูล\n\n💡 ลองค้นหาด้วยชื่ออื่น"
            else:
                response_text = "❓ กรุณาระบุชื่อโรงเรียนที่ต้องการค้นหา"
                
        elif parsed.intent == QueryIntent.SCHOOL_COUNT:
            response_text = self._handle_school_count(parsed, message, school_engine, synthesizer)
            
        elif parsed.intent == QueryIntent.SCHOOL_LIST:
            response_text = self._handle_school_list(parsed, message, school_engine, synthesizer, history)
            
        elif parsed.intent == QueryIntent.SCHOOL_SEARCH:
            response_text = self._handle_school_search(parsed, message, school_engine, history)
        
        return response_text
    def _handle_school_count(self, parsed: ParsedQuery, message: str, school_engine: SchoolSearchEngine, synthesizer: ResponseSynthesizer) -> str:
        """Handle school count queries"""
        data = {"query_type": "school_count", "location": {}, "counts": {}, "sample_schools": []}
        
        # DEBUG: Log parsed entities
        logger.info(f"🔍 Parsed: agency={parsed.agency}, province={parsed.province}, district={parsed.district}, region={parsed.region}")
        
        # Handle subdistrict-level queries (search in statistics collection)
        if parsed.subdistrict:
            # Search for subdistrict in statistics
            try:
                
                # Filter by metadata.subdistrict
                search_result = school_engine.client.scroll(
                    collection_name="education_statistics_subdistrict",
                    scroll_filter=Filter(
                        must=[
                            FieldCondition(
                                key="metadata.subdistrict",
                                match=MatchValue(value=parsed.subdistrict)
                            )
                        ]
                    ),
                    limit=20,
                    with_payload=True
                )
                
                total_count = 0
                province = None
                district = None
                subdistrict = parsed.subdistrict
                agencies_breakdown = {}
                
                for point in search_result[0]:
                    meta = point.payload.get('metadata', {})
                    if not province:
                        province = meta.get('province')
                        district = meta.get('district')
                    
                    # Get count from metadata
                    count = meta.get('count', 0)
                    agency = meta.get('agency')
                    
                    if agency:
                        # This is agency breakdown record
                        agencies_breakdown[agency] = agencies_breakdown.get(agency, 0) + count
                    elif meta.get('stat_type') == 'subdistrict_total':
                        # This is total count record
                        total_count = count
                
                # Calculate total from agencies if not set
                if total_count == 0 and agencies_breakdown:
                    total_count = sum(agencies_breakdown.values())
                
                if total_count > 0:
                    data["location"] = {"province": province, "district": district, "subdistrict": subdistrict}
                    data["counts"] = {"total": int(total_count), "agencies": agencies_breakdown}
                    
                    # Get sample schools from education_schools
                    sample_results = school_engine.client.scroll(
                        collection_name=COLLECTION_NAMES["schools"],
                        scroll_filter=Filter(
                            must=[
                                FieldCondition(
                                    key="metadata.subdistrict",
                                    match=MatchValue(value=subdistrict)
                                )
                            ]
                        ),
                        limit=10,
                        with_payload=True
                    )
                    
                    sample_schools = []
                    for s in sample_results[0]:
                        meta = s.payload.get('metadata', {})
                        sample_schools.append({
                            "name": meta.get('school_name'),
                            "district": meta.get('district'),
                            "subdistrict": meta.get('subdistrict')
                        })
                    data["sample_schools"] = sample_schools
                    
            except Exception as e:
                logger.warning(f"⚠️ Subdistrict search error: {e}")
        
        elif parsed.province:
            count = school_engine.count_schools(
                province=parsed.province,
                district=parsed.district,
                agency=parsed.agency
            )
            
            if parsed.district:
                sample_results = school_engine.search_by_district(parsed.province, parsed.district, parsed.agency, limit=10)
            else:
                sample_results = school_engine.search_by_province(parsed.province, parsed.agency, limit=10)
            
            sample_schools = []
            for s in sample_results:
                meta = s.payload.get('metadata', {})
                sample_schools.append({
                    "name": meta.get('school_name'),
                    "district": meta.get('district'),
                    "subdistrict": meta.get('subdistrict'),
                    "agency": meta.get('agency')  # Add agency to sample
                })
            
            # Get agency breakdown for the province
            agency_breakdown = {}
            subdistrict_breakdown = {}  # New: breakdown by subdistrict for district-level queries
            
            try:
                
                # Build filter conditions
                filter_conditions = [
                    FieldCondition(key="metadata.province", match=MatchValue(value=parsed.province))
                ]
                if parsed.district:
                    filter_conditions.append(
                        FieldCondition(key="metadata.district", match=MatchValue(value=parsed.district))
                    )
                
                scroll_result = school_engine.client.scroll(
                    collection_name=COLLECTION_NAMES["schools"],
                    scroll_filter=Filter(must=filter_conditions),
                    limit=2000,
                    with_payload=["metadata.agency", "metadata.subdistrict", "metadata.school_name"]
                )
                
                seen_schools = set()
                for point in scroll_result[0]:
                    meta = point.payload.get('metadata', {})
                    school_name = meta.get('school_name', '')
                    
                    if school_name not in seen_schools:
                        seen_schools.add(school_name)
                        
                        # Agency breakdown
                        agency = meta.get('agency')
                        if agency:
                            agency_breakdown[agency] = agency_breakdown.get(agency, 0) + 1
                        
                        # Subdistrict breakdown (only for district-level queries)
                        if parsed.district:
                            subdistrict = meta.get('subdistrict')
                            if subdistrict:
                                subdistrict_breakdown[subdistrict] = subdistrict_breakdown.get(subdistrict, 0) + 1
                
            except Exception as e:
                logger.warning(f"⚠️ Breakdown error: {e}")
            
            data["location"] = {"province": parsed.province, "district": parsed.district, "agency": parsed.agency}
            counts_data = {"total": count, "agency_breakdown": agency_breakdown}
            
            # Add subdistrict breakdown for district-level queries
            if parsed.district and subdistrict_breakdown:
                # Sort by count descending
                sorted_subdistricts = sorted(subdistrict_breakdown.items(), key=lambda x: x[1], reverse=True)
                counts_data["subdistrict_breakdown"] = [{"subdistrict": s, "count": c} for s, c in sorted_subdistricts]
            
            data["counts"] = counts_data
            data["sample_schools"] = sample_schools
            
        elif parsed.region and parsed.region != "each_region":
            provinces_in_region = REGIONS.get(parsed.region, [])
            total_count = 0
            province_breakdown = []
            agency_breakdown = {}
            sample_schools = []
            
            for province in provinces_in_region:
                count = school_engine.count_schools(province=province, agency=parsed.agency)
                total_count += count
                if count > 0:
                    province_breakdown.append({"province": province, "count": count})
                
                # Collect agency counts from this province
                try:
                    agency_scroll = school_engine.client.scroll(
                        collection_name=COLLECTION_NAMES["schools"],
                        scroll_filter=Filter(must=[
                            FieldCondition(key="metadata.province", match=MatchValue(value=province))
                        ]),
                        limit=500,
                        with_payload=["metadata.agency"]
                    )
                    for point in agency_scroll[0]:
                        agency = point.payload.get('metadata', {}).get('agency')
                        if agency:
                            agency_breakdown[agency] = agency_breakdown.get(agency, 0) + 1
                except:
                    pass
            
            # Get sample schools from first province with data
            for province in provinces_in_region:
                if not sample_schools:
                    samples = school_engine.search_by_province(province, parsed.agency, limit=10)
                    for s in samples:
                        meta = s.payload.get('metadata', {})
                        sample_schools.append({
                            "name": meta.get('school_name'),
                            "district": meta.get('district'),
                            "province": meta.get('province'),
                            "agency": meta.get('agency')
                        })
                    if sample_schools:
                        break
            
            data["location"] = {"region": parsed.region, "agency": parsed.agency}
            data["counts"] = {
                "total": total_count,
                "province_breakdown": sorted(province_breakdown, key=lambda x: x['count'], reverse=True)[:10],
                "agency_breakdown": agency_breakdown
            }
            data["sample_schools"] = sample_schools
        
        # Handle national/country-wide queries (ทั้งประเทศ, ประเทศไทย) - NOT agency-only
        elif not parsed.province and not parsed.district and not parsed.region and not parsed.agency:
            # Check if this looks like a national query
            national_keywords = ['ประเทศ', 'ทั้งประเทศ', 'ทั่วประเทศ', 'ไทย']
            is_national = any(kw in message for kw in national_keywords)
            
            if is_national:
                total_count = 0
                agency_breakdown = {}
                sample_schools = []
                
                # Aggregate across all regions
                for region_name, provinces in REGIONS.items():
                    if region_name in ['ภาคอีสาน', 'ภาคอีสาน']:  # Skip aliases
                        continue
                    for province in provinces:
                        count = school_engine.count_schools(province=province)
                        total_count += count
                        
                        # Get agency breakdown
                        try:
                            agency_scroll = school_engine.client.scroll(
                                collection_name=COLLECTION_NAMES["schools"],
                                scroll_filter=Filter(must=[
                                    FieldCondition(key="metadata.province", match=MatchValue(value=province))
                                ]),
                                limit=200,
                                with_payload=["metadata.agency"]
                            )
                            for point in agency_scroll[0]:
                                agency = point.payload.get('metadata', {}).get('agency')
                                if agency:
                                    agency_breakdown[agency] = agency_breakdown.get(agency, 0) + 1
                        except:
                            pass
                
                # Get sample schools from one province
                samples = school_engine.search_by_province("กรุงเทพมหานคร", limit=10)
                for s in samples:
                    meta = s.payload.get('metadata', {})
                    sample_schools.append({
                        "name": meta.get('school_name'),
                        "district": meta.get('district'),
                        "province": meta.get('province'),
                        "agency": meta.get('agency')
                    })
                
                data["location"] = {"country": "ประเทศไทย"}
                data["counts"] = {"total": total_count, "agency_breakdown": agency_breakdown}
                data["sample_schools"] = sample_schools
        
        # Handle agency-only queries (e.g., "สพฐ มีกี่โรงเรียน")
        elif parsed.agency and not parsed.province and not parsed.region:
            # Count schools by agency nationwide
            
            total_count = 0
            sample_schools = []
            province_breakdown = {}
            
            # Count all schools with this agency
            scroll_result = school_engine.client.scroll(
                collection_name=COLLECTION_NAMES["schools"],
                scroll_filter=Filter(must=[
                    FieldCondition(key="metadata.agency", match=MatchValue(value=parsed.agency))
                ]),
                limit=5000,
                with_payload=["metadata.province", "metadata.school_name", "metadata.district"]
            )
            
            seen_schools = set()
            for point in scroll_result[0]:
                meta = point.payload.get('metadata', {})
                school_name = meta.get('school_name', '')
                if school_name not in seen_schools:
                    seen_schools.add(school_name)
                    total_count += 1
                    
                    # Province breakdown
                    province = meta.get('province', 'ไม่ระบุ')
                    province_breakdown[province] = province_breakdown.get(province, 0) + 1
                    
                    # Collect samples
                    if len(sample_schools) < 10:
                        sample_schools.append({
                            "name": school_name,
                            "district": meta.get('district'),
                            "province": province
                        })
            
            # Sort province breakdown by count
            sorted_provinces = sorted(province_breakdown.items(), key=lambda x: x[1], reverse=True)[:10]
            
            data["location"] = {"agency": parsed.agency}
            data["counts"] = {"total": total_count, "province_breakdown": [{"province": p, "count": c} for p, c in sorted_provinces]}
            data["sample_schools"] = sample_schools
        
        # DEBUG: Log data before synthesize
        logger.info(f"📦 Data for synthesize: total={data['counts'].get('total', 0)}, samples={len(data.get('sample_schools', []))}")
        
        llm_response = synthesizer.synthesize("SCHOOL_COUNT", data, message)
        
        if llm_response:
            return llm_response
        else:
            # Smart fallback template - context-aware and natural
            total_count = data['counts'].get('total', 0)
            
            # Build location description
            if parsed.region:
                location_desc = f"ภาค{parsed.region.replace('ภาค', '')}"
            elif parsed.district and parsed.province:
                location_desc = f"เขต/อำเภอ{parsed.district} จังหวัด{parsed.province}"
            elif parsed.province:
                location_desc = f"จังหวัด{parsed.province}"
            else:
                location_desc = "ทั่วประเทศไทย"
            
            # Add agency context
            if parsed.agency:
                location_desc += f" สังกัด{parsed.agency}"
            
            # Natural intro based on context
            response = f"📊 **ข้อมูลโรงเรียนใน{location_desc}**\n\n"
            response += f"พบโรงเรียนทั้งหมด **{total_count:,}** แห่ง"
            
            # Add context-specific observation
            if total_count > 1000:
                response += " ซึ่งถือว่าเป็นพื้นที่ที่มีโรงเรียนจำนวนมาก"
            elif total_count > 100:
                response += " ครอบคลุมหลายพื้นที่ในเขตนี้"
            elif total_count > 0:
                response += ""
            response += "\n\n"
            
            # Add agency breakdown if available
            if data['counts'].get('agency_breakdown'):
                response += "🏛️ **แยกตามสังกัด**\n"
                sorted_agencies = sorted(data['counts']['agency_breakdown'].items(), key=lambda x: x[1], reverse=True)
                for agency, count in sorted_agencies[:5]:
                    response += f"• {agency}: {count:,} แห่ง\n"
                response += "\n"
            
            # Add subdistrict breakdown for district queries
            if data['counts'].get('subdistrict_breakdown'):
                response += "🗺️ **แยกตามตำบล/แขวง**\n"
                for item in data['counts']['subdistrict_breakdown'][:8]:
                    response += f"• {item['subdistrict']}: {item['count']:,} แห่ง\n"
                response += "\n"
            
            # Add province breakdown for region queries
            if data['counts'].get('province_breakdown'):
                response += "📈 **แยกตามจังหวัด**\n"
                for i, p in enumerate(data['counts']['province_breakdown'][:5], 1):
                    response += f"{i}. {p['province']}: {p['count']:,} แห่ง\n"
                response += "\n"
            
            # Add sample schools if available
            if data.get("sample_schools"):
                response += "🏫 **ตัวอย่างโรงเรียน**\n"
                for school in data["sample_schools"][:5]:
                    name = school.get("name", "-")
                    district = school.get("district", "")
                    subdistrict = school.get("subdistrict", "")
                    loc_part = subdistrict or district
                    response += f"• {name}"
                    if loc_part:
                        response += f" ({loc_part})"
                    response += "\n"
                response += "\n"
            
            # Smart follow-up suggestions
            response += "💡 **สามารถถามต่อได้**\n"
            if parsed.district:
                response += f"• ตำบลไหนใน{parsed.district}มีโรงเรียนมากที่สุด?\n"
                response += f"• โรงเรียนเอกชนใน{parsed.district}มีกี่แห่ง?\n"
            elif parsed.province:
                response += f"• อำเภอไหนใน{parsed.province}มีโรงเรียนมากที่สุด?\n"
                response += f"• โรงเรียนสังกัด สพฐ ใน{parsed.province}มีกี่แห่ง?\n"
            elif parsed.region:
                response += f"• จังหวัดไหนใน{parsed.region}มีโรงเรียนน้อยที่สุด?\n"
                response += f"• โรงเรียนเอกชนใน{parsed.region}มีกี่แห่ง?\n"
            elif parsed.agency:
                response += f"• จังหวัดไหนมี{parsed.agency}มากที่สุด?\n"
                response += "• ภาคไหนมีโรงเรียนสังกัดนี้มากที่สุด?\n"
            
            return response
    def _handle_school_list(self, parsed: ParsedQuery, message: str, school_engine: SchoolSearchEngine, synthesizer: ResponseSynthesizer, history: List) -> str:
        """Handle school list queries"""
        data = {"query_type": "school_list", "location": {}, "total": 0, "schools": [], "district_breakdown": []}
        results = []
        location = ""
        total = 0
        
        if parsed.subdistrict:
            # Handle subdistrict search (PRIORITY)
            results = school_engine.search_by_subdistrict(
                province=parsed.province, 
                subdistrict=parsed.subdistrict, 
                district=parsed.district,
                agency=parsed.agency,
                limit=15
            )
            location = f"ต.{parsed.subdistrict}"
            if parsed.district: location += f" อ.{parsed.district}"
            if parsed.province: location += f" จ.{parsed.province}"
            
            # Count for subdistrict (approximate since no dedicated count method yet, use len(results) or search all)
            # For now, we will trust the search result length or implement count later if needed. 
            # But the UI expects 'total'. Let's do a quick count by fetching more keys if needed, 
            # or just use len(results) if < limit. 
            # Actually, let's just use the length of results for now as subdistricts rarely have > 15 schools.
            total = len(results) 
            # If we hit limit, we might want to know if there are more... 
            # Optimally we should add count_schools_by_subdistrict, but for now let's assume < 15 or close enough.
            
            data["location"] = {
                "province": parsed.province, 
                "district": parsed.district, 
                "subdistrict": parsed.subdistrict,
                "agency": parsed.agency
            }

        elif parsed.district and parsed.province:
            results = school_engine.search_by_district(parsed.province, parsed.district, parsed.agency, limit=15)
            location = f"อ.{parsed.district} จ.{parsed.province}"
            total = school_engine.count_schools(parsed.province, parsed.district, parsed.agency)
            data["location"] = {"province": parsed.province, "district": parsed.district, "agency": parsed.agency}
            
        elif parsed.province:
            results = school_engine.search_by_province(parsed.province, parsed.agency, limit=15)
            location = f"จ.{parsed.province}"
            total = school_engine.count_schools(parsed.province, agency=parsed.agency)
            data["location"] = {"province": parsed.province, "agency": parsed.agency}
            
        elif parsed.region and parsed.region != "each_region":
            provinces_in_region = REGIONS.get(parsed.region, [])
            all_results = []
            province_stats = []
            for province in provinces_in_region:
                province_results = school_engine.search_by_province(province, parsed.agency, limit=5)
                count = school_engine.count_schools(province=province, agency=parsed.agency)
                all_results.extend(province_results)
                total += count
                if count > 0:
                    province_stats.append({"province": province, "count": count})
            results = all_results[:15]
            location = parsed.region
            data["location"] = {"region": parsed.region, "agency": parsed.agency}
            data["district_breakdown"] = sorted(province_stats, key=lambda x: x['count'], reverse=True)[:8]
        else:
            return "❓ กรุณาระบุจังหวัด อำเภอ หรือภูมิภาคที่ต้องการค้นหา"
        
        data["total"] = total
        for hit in results[:15]:
            meta = hit.payload.get('metadata', {})
            data["schools"].append({
                "name": meta.get('school_name'),
                "district": meta.get('district'),
                "subdistrict": meta.get('subdistrict'),
                "agency": meta.get('agency')
            })
        
        if results:
            llm_response = synthesizer.synthesize("SCHOOL_LIST", data, message)
            
            if llm_response:
                response_text = llm_response
                if total > 15:
                    response_text += f"\n\n💡 **พิมพ์ \"ดูเพิ่มเติม\" เพื่อดูโรงเรียนต่อไป** (เหลืออีก {total - 15:,} แห่ง)"
            else:
                response_text = f"📊 **{location}** มีโรงเรียนทั้งหมด **{total:,}** แห่ง\n\n📚 **รายชื่อ:**\n"
                for i, hit in enumerate(results[:15], 1):
                    meta = hit.payload.get('metadata', {})
                    response_text += f"{i}. **{meta.get('school_name')}** (อ.{meta.get('district')})\n"
            
            # Save pagination context
            if total > 15:
                self.memory.last_school_list_offset = 15
                self.memory.last_school_list_query = {
                    'province': parsed.province,
                    'district': parsed.district,
                    'agency': parsed.agency,
                    'region': parsed.region,
                    'total': total
                }
            
            return response_text
        else:
            return f"❌ ไม่พบโรงเรียนใน{location}"
    def _handle_school_search(self, parsed: ParsedQuery, message: str, school_engine: SchoolSearchEngine, history: List) -> str:
        """Handle school search by name"""
        # If region or province specified without school name, redirect to list
        if (parsed.region or parsed.province) and not parsed.school_name:
            synthesizer = ResponseSynthesizer()
            return self._handle_school_list(parsed, message, school_engine, synthesizer, history)
        
        # Clean school name
        clean_name = message
        remove_phrases = [
            'หาโรงเรียน', 'ค้นหาโรงเรียน', 'โรงเรียน', 
            'ขอรายละเอียด', 'รายละเอียด', 'ขอข้อมูล', 'ข้อมูล', 
            'ขอเบอร์โทร', 'เบอร์โทร', 'ที่อยู่', 'รบกวนขอ', 'ขอ',
            'ช่วยหา', 'หา', 'ให้หน่อย', 'หน่อย', 'ครับ', 'ค่ะ',
            'สพฐ', 'อปท', 'เอกชน', 'กทม', 'ภาคใต้', 'ภาคเหนือ', 'ภาคอีสาน', 'ภาคกลาง', 'ภาคตะวันออก'
        ]
        for phrase in remove_phrases:
            clean_name = clean_name.replace(phrase, '')
        
        clean_name = re.sub(r'[\(\[].*?[\)\]]', '', clean_name).strip()
        school_name = clean_name
        
        if school_name and len(school_name) > 2:
            results = school_engine.search_by_name(school_name, limit=10)
            if results:
                response_text = f"🔍 **ผลการค้นหา \"{school_name}\"**\n\n"
                for i, hit in enumerate(results[:10], 1):
                    meta = hit.payload.get('metadata', {})
                    name = meta.get('school_name', 'ไม่ระบุ')
                    province = meta.get('province', '-')
                    district = meta.get('district', '-')
                    agency = meta.get('agency', '-')
                    response_text += f"{i}. **{name}**\n   📍 อ.{district} จ.{province}\n   🏢 {agency[:20]}...\n\n"
                return response_text
            else:
                # Try fuzzy matching
                similar_schools = school_engine.find_similar_schools(school_name, province=parsed.province, top_k=5)
                
                if similar_schools:
                    response_text = f"🤔 **คุณหมายถึง...?** (ไม่พบ \"{school_name}\" ตรงๆ)\n\n"
                    response_text += "📋 **โรงเรียนที่ใกล้เคียง:**\n"
                    for i, school in enumerate(similar_schools, 1):
                        score_pct = int(school['score'] * 100)
                        response_text += f"{i}. **{school['name']}** ({score_pct}% ตรงกัน)\n"
                        response_text += f"   📍 อ.{school['district']} จ.{school['province']}\n\n"
                    response_text += "\n💡 *ลองคลิกหรือพิมพ์ชื่อที่ถูกต้องอีกครั้งนะครับ*"
                    return response_text
                else:
                    return self._rag_fallback(message)
        else:
            return self._rag_fallback(message)
    def _handle_load_more(self) -> str:
        """Handle load more pagination"""
        last_query = getattr(self.memory, 'last_school_list_query', None)
        current_offset = getattr(self.memory, 'last_school_list_offset', 0)
        
        if last_query and current_offset > 0:
            school_engine = SchoolSearchEngine(self.qdrant_client)
            
            # --- Advanced Search Pagination ---
            if last_query.get('type') == 'advanced_criteria':
                filters = last_query.get('filters', {})
                total = last_query.get('total', 0)
                
                # Fetch next page using same criteria
                results, _, _ = school_engine.search_by_criteria(filters, limit=15, offset=current_offset)
                
                if results:
                    criteria_text = []
                    if filters.get('min_students'): criteria_text.append(f"นักเรียน > {filters['min_students']}")
                    if filters.get('area_name'): criteria_text.append(f"สังกัด {filters['area_name']}")
                    criteria_str = ", ".join(criteria_text)
                    
                    response_text = f"📚 **ผลการค้นหาต่อ** ({criteria_str}):\n\n"
                    
                    for i, hit in enumerate(results, current_offset + 1):
                        meta = hit.payload.get('metadata', {})
                        school_name = meta.get('school_name', 'ไม่ระบุ')
                        summ = f"{meta.get('total_students', 0)} คน" if filters.get('min_students') or filters.get('max_students') else ""
                        response_text += f"{i}. **{school_name}** {summ}\n"
                    
                    new_offset = current_offset + len(results)
                    remaining = total - new_offset
                    
                    if remaining > 0:
                        response_text += f"\n*...และอีก {remaining:,} แห่ง*"
                        response_text += f"\n\n💡 **พิมพ์ \"ดูเพิ่มเติม\" เพื่อดูต่อ**"
                        self.memory.last_school_list_offset = new_offset
                    else:
                        response_text += f"\n\n✅ **แสดงครบทั้งหมดแล้ว!**"
                        self.memory.last_school_list_offset = 0
                        self.memory.last_school_list_query = None
                    
                    return response_text
                else:
                    self.memory.last_school_list_offset = 0
                    return "✅ **แสดงครบทั้งหมดแล้ว!**"

            # --- Compatible Legacy Pagination ---
            province = last_query.get('province')
            district = last_query.get('district')
            agency = last_query.get('agency')
            total = last_query.get('total', 0)
            
            if district and province:
                all_results = school_engine.search_by_district(province, district, agency, limit=total)
            elif province:
                all_results = school_engine.search_by_province(province, agency, limit=total)
            else:
                all_results = []
            
            results = all_results[current_offset:current_offset + 15]
            
            if results:
                location = f"จ.{province}" if not district else f"อ.{district} จ.{province}"
                agency_text = f" สังกัด{agency}" if agency else ""
                
                response_text = f"📚 **รายชื่อโรงเรียนต่อ** ({location}{agency_text}):\n\n"
                
                for i, hit in enumerate(results, current_offset + 1):
                    meta = hit.payload.get('metadata', {})
                    school_name = meta.get('school_name', 'ไม่ระบุ')
                    dist = meta.get('district', '-')
                    subdistrict = meta.get('subdistrict', '-')
                    response_text += f"{i}. **{school_name}** (ต.{subdistrict}, อ.{dist})\n"
                
                new_offset = current_offset + len(results)
                remaining = total - new_offset
                
                if remaining > 0:
                    response_text += f"\n*...และอีก {remaining:,} แห่ง*"
                    response_text += f"\n\n💡 **พิมพ์ \"ดูเพิ่มเติม\" เพื่อดูโรงเรียนต่อไป**"
                    self.memory.last_school_list_offset = new_offset
                else:
                    response_text += f"\n\n✅ **แสดงครบทั้งหมดแล้ว!**"
                    self.memory.last_school_list_offset = 0
                    self.memory.last_school_list_query = None
                
                return response_text
            else:
                self.memory.last_school_list_offset = 0
                return "✅ **แสดงครบทั้งหมดแล้ว!**"
        else:
            return "❓ ไม่มีข้อมูลให้แสดงเพิ่มเติม กรุณาค้นหารายชื่อโรงเรียนใหม่ก่อน"
    def _handle_advanced_search(self, parsed: ParsedQuery, message: str, school_engine: SchoolSearchEngine, synthesizer: ResponseSynthesizer, history: List) -> str:
        """Handle comprehensive data queries (students, teachers, area, coordinates, person_type)"""
        
        # --- PERSONNEL TYPE QUERY HANDLING ---
        if parsed.person_type:
            filters = {
                'person_type': parsed.person_type,
                'school_name': parsed.school_name,
                'province': parsed.province
            }
            filters = {k: v for k, v in filters.items() if v is not None}
            
            results = school_engine.search_teachers(filters)
            
            if not results:
                msg = f"เสียดายครับ ไม่พบข้อมูล '{parsed.person_type}' "
                if parsed.school_name: msg += f"ของโรงเรียน {parsed.school_name} ครับ"
                elif parsed.province: msg += f"ในจังหวัด {parsed.province} ครับ"
                else: msg += "ครับ"
                return msg
            
            # Calculate total from 'metadata.count' or 'count'
            total_personnel = 0
            for r in results:
                meta = r.get('metadata', r)  # Handle both nested and flat
                total_personnel += meta.get('count', 0)
            
            # Direct response for specific school
            if parsed.school_name and len(results) > 0:
                meta = results[0].get('metadata', results[0])
                count = meta.get('count', 0)
                return f"โรงเรียน **{parsed.school_name}** มี **{parsed.person_type}** จำนวน **{count}** คนครับ"
            
            # Aggregate response
            msg = f"📊 ข้อมูล **{parsed.person_type}** "
            if parsed.province: msg += f"ในจังหวัด {parsed.province}"
            msg += f"\n\nพบข้อมูลทั้งหมด **{total_personnel:,}** คน (จาก {len(results)} รายการ)"
            return msg
        
        # --- STANDARD SCHOOL SEARCH ---
        # Build filter dict
        filters = {
            'province': parsed.province,
            'district': parsed.district,
            'subdistrict': parsed.subdistrict,
            'agency': parsed.agency,
            'area_name': parsed.area_name,
            'min_students': parsed.min_students,
            'max_students': parsed.max_students,
            'min_teachers': parsed.min_teachers,
            'max_teachers': parsed.max_teachers
        }
        
        # Remove None values
        filters = {k: v for k, v in filters.items() if v is not None}
        
        results, total_count, _ = school_engine.search_by_criteria(filters, limit=15)
        
        data = {
            "query_type": "advanced_search",
            "filters": filters,
            "total": total_count,
            "schools": []
        }
        
        for hit in results:
            meta = hit.payload.get('metadata', {})
            school_data = {
                "name": meta.get('school_name'),
                "province": meta.get('province'),
                "district": meta.get('district'),
                "subdistrict": meta.get('subdistrict'),
                "agency": meta.get('agency'),
                "total_students": meta.get('total_students', 0),
                "total_teachers": meta.get('total_teachers', 0),
                "lat": meta.get('lat'),
                "lon": meta.get('lon'),
                "area_name": meta.get('area_name')
            }
            data["schools"].append(school_data)
            
        llm_response = synthesizer.synthesize("ADVANCED_SEARCH", data, message)
        
        if llm_response:
            response_text = llm_response
        else:
            # Fallback
            criteria_text = []
            if parsed.min_students: criteria_text.append(f"นักเรียน > {parsed.min_students}")
            if parsed.area_name: criteria_text.append(f"สังกัด {parsed.area_name}")
            
            criteria_str = ", ".join(criteria_text)
            response_text = f"🔍 **ผลการค้นหา** ({criteria_str})\n พบทั้งหมด **{total_count:,}** โรงเรียน\n\n"
            
            for i, school in enumerate(data["schools"], 1):
                summ = f"{school['total_students']} คน" if parsed.min_students or parsed.max_students else ""
                response_text += f"{i}. **{school['name']}** {summ}\n"
                
        # Pagination Logic
        if total_count > 15:
            response_text += f"\n\n💡 **พิมพ์ \"ดูเพิ่มเติม\" เพื่อดูต่อ** (เหลืออีก {total_count - 15:,} แห่ง)"
            
            # Save context for Load More
            self.memory.last_school_list_offset = 15
            self.memory.last_school_list_query = {
                'type': 'advanced_criteria', # Marker for advanced search
                'filters': filters,
                'total': total_count
            }
            
        return response_text
