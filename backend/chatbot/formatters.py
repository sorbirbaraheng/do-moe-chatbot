"""
Response Formatter for Education Chatbot
Formats search results into user-friendly responses with charts
"""

import json
import logging
from typing import Generator, List, Optional

import google.generativeai as genai

from .types import SearchResult, ParsedQuery, QueryIntent, QueryLevel

logger = logging.getLogger(__name__)


class ResponseFormatter:
    """Format responses for different query types"""
    
    def __init__(self, model: Optional[genai.GenerativeModel] = None, model_name: str = 'models/gemini-1.5-flash'):
        self.model = model
        self.model_name = model_name
        self.level_names = {
            QueryLevel.PROVINCE: "จังหวัด",
            QueryLevel.DISTRICT: "อำเภอ/เขต",
            QueryLevel.SUBDISTRICT: "ตำบล/แขวง",
            QueryLevel.AGENCY: "สังกัด"
        }
    
    @staticmethod
    def format_location(name: str, level: QueryLevel) -> str:
        """Format location name"""
        if '|' not in name:
            return name
        
        if level == QueryLevel.PROVINCE:
            return f"จังหวัด{name}"
        elif level == QueryLevel.DISTRICT:
            parts = name.split('|')
            if len(parts) < 2:
                return name
            is_bangkok = 'กรุงเทพ' in parts[0]
            term = "เขต" if is_bangkok else "อำเภอ"
            return f"{term}{parts[1]} ({parts[0]})"
        elif level == QueryLevel.SUBDISTRICT:
            parts = name.split('|')
            if len(parts) < 3:
                return name
            is_bangkok = 'กรุงเทพ' in parts[0]
            sub_term = "แขวง" if is_bangkok else "ตำบล"
            return f"{sub_term}{parts[2]} ({parts[1]}, {parts[0]})"
        elif level == QueryLevel.AGENCY:
            return name
        return name
    
    def format(self, result: SearchResult, parsed_query: ParsedQuery) -> Generator[str, None, None]:
        """Format search results into response"""
        
        # No data found
        if not result.data:
            if self.model: 
                yield from self._generate_general_knowledge_response(parsed_query)
                return
            else:
                yield "😔 **น้องดีโอหาข้อมูลในระบบไม่เจอครับ**\n\n"
                return
        
        intent = parsed_query.intent
        level = parsed_query.level
        
        # Add AI Insight
        ai_insight_text = ""
        if self.model:
            try:
                for chunk in self._generate_ai_insight(result, parsed_query):
                    ai_insight_text += chunk
                    yield chunk
                if ai_insight_text:
                    yield "\n\n---\n\n"
            except Exception as e:
                logger.warning(f"AI Insight skipped: {e}")
        
        # Structured Response
        if intent in [QueryIntent.RANKING_MOST, QueryIntent.RANKING_LEAST]:
            yield from self._format_ranking(result, level, parsed_query)
        elif len(result.data) == 1:
            yield from self._format_single(result, level, parsed_query)
        else:
            yield from self._format_listing(result, level, parsed_query)

    def _generate_ai_insight(self, result: SearchResult, parsed_query: ParsedQuery) -> Generator[str, None, None]:
        """Generate AI insight/explanation of the data"""
        try:
            summary_items = []
            for name, data in result.data[:10]:
                summary_items.append(f"{name} ({data['total']} แห่ง)")
            
            prompt = f"""
role: คุณคือ "น้องดีโอ" (DO-MOE) ผู้ช่วยอัจฉริยะที่เชี่ยวชาญสถิติการศึกษาและมีหัวใจบริการ
style: พูดจาฉะฉาน เป็นกันเอง (ครับ/ผม) สุภาพแต่อบอุ่น แฝงความรอบรู้ + Emoji ✨
task: วิเคราะห์ข้อมูลสถิติที่น้องดีโอหามาให้พี่ๆ ได้อย่าง "ลึกซึ้ง" และ "เป็นธรรมชาติ"
      - ห้ามพูดเหมือนหุ่นยนต์ หรือสรุปแค่ตัวเลข
      - ให้วิเคราะห์ภาพรวม เช่น "จะเห็นได้ว่าในพื้นที่นี้มีสัดส่วนของโรงเรียนเอกชนเยอะกว่าปกติ ซึ่งสะท้อนถึง..."
      - เปรียบเทียบจุดที่น่าสนใจหรือสังเกตเห็นจากข้อมูล
      - ความยาว 3-4 ประโยคที่ดูมีคุณค่าและเป็นมืออาชีพ

data overview: {', '.join(summary_items)}
query context: {parsed_query.original_query}

answer (Nong Dio style):
"""
            response = self.model.generate_content(prompt, stream=True)
            for chunk in response:
                yield chunk.text
        except Exception as e:
            logger.error(f"AI Insight error: {e}")
            return

    def _generate_general_knowledge_response(self, parsed_query: ParsedQuery) -> Generator[str, None, None]:
        """Generate response using LLM General Knowledge"""
        try:
            prompt = f"""
role: คุณคือ "น้องดีโอ" (DO-MOE AI)
style: น่ารัก เป็นกันเอง สุภาพ (ครับ/ผม) + Emoji 🌟
situation: ไม่พบข้อมูลในฐานข้อมูลเฉพาะทาง เลยต้องตอบด้วยความรู้ทั่วไป
task: ตอบคำถามนี้โดยใช้ความรู้ของคุณเอง

question: {parsed_query.original_query}

instruction:
1. ตอบให้เหมือนผู้เชี่ยวชาญการศึกษา
2. ห้ามบอกว่า "ไม่พบข้อมูล" หรือ "ไม่มีข้อมูล"
3. ตอบให้เป็นธรรมชาติ
4. ถ้าคำถามเฉพาะเจาะจงมากเกินไป ให้ตอบกลางๆ หรือคาดการณ์อย่างมีหลักการ

answer:
"""
            response = self.model.generate_content(prompt, stream=True)
            for chunk in response:
                yield chunk.text
                
        except Exception as e:
            logger.error(f"General Knowledge Error: {e}")
            if "quota" in str(e).lower() and self.model_name != 'models/gemini-1.5-flash-latest':
                try:
                    fallback_model = genai.GenerativeModel('models/gemini-1.5-flash-latest')
                    response = fallback_model.generate_content(prompt, stream=True)
                    for chunk in response:
                        yield chunk.text
                    return
                except:
                    pass
            yield "😅 ขอโทษครับ น้องดีโอประมวลผลไม่ไหว รบกวนพี่ลองถามใหม่นะครับ"

    def _format_chart_data(self, chart_type: str, data_points: List[dict], title: str = "") -> str:
        """Generate chart data block"""
        payload = {"type": chart_type, "data": data_points, "title": title}
        return f"\n\n<chart>{json.dumps(payload, ensure_ascii=False)}</chart>"

    def _format_ranking(self, result: SearchResult, level: QueryLevel, parsed_query: ParsedQuery) -> Generator[str, None, None]:
        """Format ranking response"""
        is_least = result.is_least
        num_show = min(10, len(result.data))
        
        emoji = "🥇" if not is_least else "📊"
        title = "น้อยที่สุด" if is_least else "มากที่สุด"
        loc_type = self.level_names.get(level, "รายการ")
        
        yield f"### {emoji} ผลการจัดอันดับ{loc_type}ที่มีโรงเรียน{title}ครับ\n\n"
        yield "น้องดีโอสรุปข้อมูลมาให้ตามนี้เลยครับ 👇\n\n"
        
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        
        chart_data = []
        
        for i, (name, data) in enumerate(result.data[:num_show], 1):
            medal = medals.get(i, "")
            if hasattr(result, 'source') and result.source.startswith('province_agencies_'):
                display = name
            else:
                display = self.format_location(name, level)
                
            chart_data.append({"name": display, "value": data['total']})
            
            if i <= 3:
                yield f"{medal} **{i}. {display}** ({data['total']:,} แห่ง)\n"
            else:
                yield f"{i}. {display}: {data['total']:,} แห่ง\n"
        
        total_all = sum(d['total'] for _, d in result.data)
        yield f"\n\n✨ *พบข้อมูลทั้งหมด {len(result.data)} รายการ (รวม {total_all:,} โรงเรียน) ครับ*\n"
        
        yield self._format_chart_data("bar", chart_data, f"สถิติ{title}")
    
    def _format_single(self, result: SearchResult, level: QueryLevel, parsed_query: ParsedQuery) -> Generator[str, None, None]:
        """Format single result"""
        name, data = result.data[0]
        if hasattr(result, 'source') and result.source.startswith('province_agencies_'):
             display = name
        else:
             display = self.format_location(name, level)
        
        yield f"### 📊 ข้อมูลจำนวนโรงเรียนใน {display} ครับ\n\n"
        
        if data['agencies']:
            yield "✨ **แยกตามสังกัดดังนี้ครับ:**\n\n"
            
            chart_data = []
            
            for agency, count in sorted(data['agencies'].items(), key=lambda x: x[1], reverse=True):
                yield f"- {agency}: **{count:,}** แห่ง\n"
                chart_data.append({"name": agency, "value": count})
                
            yield f"\n**รวมทั้งหมด:** **{data['total']:,}** แห่ง\n"
            
            yield self._format_chart_data("pie", chart_data, f"สัดส่วนสังกัด {display}")
            
        else:
            yield f"**รวมทั้งหมด:** **{data['total']:,}** แห่ง\n"
    
    def _format_listing(self, result: SearchResult, level: QueryLevel, parsed_query: ParsedQuery) -> Generator[str, None, None]:
        """Format listing response"""
        yield "✨ **ข้อมูลสรุปที่น้องคัดสรรมาให้ครับ:**\n\n"
        
        chart_data = []
        
        for i, (name, data) in enumerate(result.data[:10], 1):
            if hasattr(result, 'source') and result.source.startswith('province_agencies_'):
                display = name
            else:
                display = self.format_location(name, level)
            
            yield f"**{i}. {display}**: {data['total']:,} แห่ง\n"
            
            chart_data.append({"name": display, "value": data['total']})
        
        if len(result.data) > 10:
            yield f"\n*...และอีก {len(result.data) - 10} รายการ*\n"
            
        if len(chart_data) > 1:
             yield self._format_chart_data("bar", chart_data, f"เปรียบเทียบจำนวนโรงเรียน")
    
    def _format_summary(self, result: SearchResult, level: QueryLevel, parsed_query: ParsedQuery) -> Generator[str, None, None]:
        """Format summary response"""
        yield f"### 📊 สรุปข้อมูล ({len(result.data)} รายการ)\n\n"
        
        for i, (name, data) in enumerate(result.data[:5], 1):
            display = self.format_location(name, level)
            yield f"**{i}.** {display}: **{data['total']:,}** แห่ง\n"
        
        total_all = sum(d['total'] for _, d in result.data)
        yield f"\n**รวมทั้งหมด:** **{total_all:,}** โรงเรียน\n"
