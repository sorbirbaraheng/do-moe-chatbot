"""
🛠️ Education Chatbot Tools
Defines all available tools that the LLM can call to answer education queries.
Uses Function Calling pattern similar to ChatGPT.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json

@dataclass
class ToolParameter:
    """Definition of a tool parameter"""
    name: str
    description: str
    required: bool = False
    enum: Optional[List[str]] = None

@dataclass
class Tool:
    """Definition of a callable tool"""
    name: str
    description: str
    parameters: List[ToolParameter]
    
    def to_dict(self) -> dict:
        """Convert to dict for LLM prompt"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                p.name: {
                    "description": p.description,
                    "required": p.required,
                    **({"enum": p.enum} if p.enum else {})
                }
                for p in self.parameters
            }
        }

# ============================================================
# TOOL DEFINITIONS
# ============================================================

EDUCATION_TOOLS: List[Tool] = [
    Tool(
        name="search_schools",
        description="ค้นหาข้อมูลโรงเรียน รวมถึงที่อยู่ จำนวนนักเรียน จำนวนครู สังกัด และข้อมูลทั่วไป",
        parameters=[
            ToolParameter("school_name", "ชื่อโรงเรียน เช่น เตรียมอุดมศึกษา, สวนกุหลาบวิทยาลัย", required=False),
            ToolParameter("province", "จังหวัด เช่น กรุงเทพมหานคร, เชียงใหม่", required=False),
            ToolParameter("district", "อำเภอหรือเขต เช่น ปทุมวัน, ดินแดง", required=False),
            ToolParameter("agency", "สังกัด เช่น สพฐ, สช, กทม, อาชีวศึกษา", required=False),
            ToolParameter("limit", "จำนวนผลลัพธ์สูงสุด (default: 10)", required=False),
        ]
    ),
    
    Tool(
        name="count_teachers",
        description="นับจำนวนครู อาจารย์ บุคลากร ข้าราชการ พนักงานราชการ ลูกจ้าง ในโรงเรียนหรือพื้นที่",
        parameters=[
            ToolParameter("school_name", "ชื่อโรงเรียน", required=False),
            ToolParameter("province", "จังหวัด", required=False),
            ToolParameter("district", "อำเภอ/เขต", required=False),
            ToolParameter("gender", "เพศ", required=False, enum=["ชาย", "หญิง"]),
        ]
    ),
    
    Tool(
        name="count_students",
        description="นับจำนวนนักเรียน ผู้เรียน เด็ก ในโรงเรียนหรือพื้นที่ แยกตามระดับชั้นและเพศได้",
        parameters=[
            ToolParameter("school_name", "ชื่อโรงเรียน", required=False),
            ToolParameter("province", "จังหวัด", required=False),
            ToolParameter("district", "อำเภอ/เขต", required=False),
            ToolParameter("grade", "ระดับชั้น เช่น ป.1, ม.1, ปวช.1", required=False),
            ToolParameter("gender", "เพศ", required=False, enum=["ชาย", "หญิง"]),
        ]
    ),
    
    Tool(
        name="count_schools",
        description="นับจำนวนโรงเรียนในพื้นที่ แยกตามสังกัดได้",
        parameters=[
            ToolParameter("province", "จังหวัด", required=False),
            ToolParameter("district", "อำเภอ/เขต", required=False),
            ToolParameter("agency", "สังกัด", required=False),
        ]
    ),
    
    Tool(
        name="get_ratio",
        description="หาอัตราส่วนนักเรียนต่อครู ของโรงเรียนหรือพื้นที่",
        parameters=[
            ToolParameter("school_name", "ชื่อโรงเรียน", required=False),
            ToolParameter("province", "จังหวัด", required=False),
        ]
    ),
    
    Tool(
        name="compare",
        description="เปรียบเทียบข้อมูลระหว่าง 2 โรงเรียน หรือ 2 จังหวัด เช่น จำนวนนักเรียน จำนวนครู จำนวนโรงเรียน",
        parameters=[
            ToolParameter("entity1", "โรงเรียนหรือจังหวัดแรก", required=True),
            ToolParameter("entity2", "โรงเรียนหรือจังหวัดที่สอง", required=True),
            ToolParameter("metric", "สิ่งที่ต้องการเปรียบเทียบ", required=True, 
                         enum=["students", "teachers", "schools", "ratio"]),
        ]
    ),
    
    Tool(
        name="ranking",
        description="จัดอันดับ มากที่สุด/น้อยที่สุด เช่น โรงเรียนที่มีนักเรียนมากที่สุด จังหวัดที่มีครูน้อยที่สุด",
        parameters=[
            ToolParameter("metric", "สิ่งที่ต้องการจัดอันดับ", required=True,
                         enum=["students", "teachers", "schools", "ratio"]),
            ToolParameter("order", "ลำดับ", required=True, enum=["most", "least"]),
            ToolParameter("scope", "ขอบเขตการจัดอันดับ", required=False, 
                         enum=["school", "province", "district"]),
            ToolParameter("province", "จังหวัด (ถ้าต้องการจัดอันดับในจังหวัดนั้น)", required=False),
            ToolParameter("limit", "จำนวนอันดับที่แสดง (default: 5)", required=False),
        ]
    ),
    
    Tool(
        name="list_schools",
        description="แสดงรายชื่อโรงเรียนในพื้นที่ พร้อมข้อมูลย่อ",
        parameters=[
            ToolParameter("province", "จังหวัด", required=False),
            ToolParameter("district", "อำเภอ/เขต", required=False),
            ToolParameter("agency", "สังกัด", required=False),
            ToolParameter("limit", "จำนวนที่แสดง (default: 10)", required=False),
        ]
    ),
]

def get_tools_prompt() -> str:
    """Generate tools description for LLM prompt"""
    tools_list = [t.to_dict() for t in EDUCATION_TOOLS]
    return json.dumps(tools_list, ensure_ascii=False, indent=2)

def get_tool_by_name(name: str) -> Optional[Tool]:
    """Get a tool by its name"""
    for tool in EDUCATION_TOOLS:
        if tool.name == name:
            return tool
    return None

# ============================================================
# LLM PROMPTS
# ============================================================

TOOL_SELECTION_PROMPT = '''คุณเป็น AI ผู้ช่วยวิเคราะห์คำถามเกี่ยวกับข้อมูลการศึกษาไทย

## Available Tools:
{tools}

## Instructions:
1. วิเคราะห์คำถามของผู้ใช้
2. เลือก tool(s) ที่เหมาะสมที่สุดในการตอบคำถาม
3. ระบุ parameters ที่จำเป็น
4. ถ้าต้องใช้หลาย tools ให้ระบุทั้งหมด

## Rules:
- ถ้าถามเกี่ยวกับ "ครู", "อาจารย์", "บุคลากร", "ข้าราชการ" → ใช้ count_teachers
- ถ้าถามเกี่ยวกับ "นักเรียน", "ผู้เรียน", "เด็ก" → ใช้ count_students
- ถ้าถาม "เปรียบเทียบ", "ระหว่าง", "กับ" → ใช้ compare
- ถ้าถาม "มากที่สุด", "น้อยที่สุด", "อันดับ" → ใช้ ranking
- ถ้าถาม "มีกี่โรงเรียน", "จำนวนโรงเรียน" → ใช้ count_schools
- ถ้าถาม "อัตราส่วน", "ต่อครู" → ใช้ get_ratio
- ถ้าถาม "รายชื่อโรงเรียน", "โรงเรียนอะไรบ้าง" → ใช้ list_schools
- ถ้าถามข้อมูลทั่วไปของโรงเรียน → ใช้ search_schools

## User Question:
{question}

## Response Format (JSON only, no explanation):
[
  {{"name": "tool_name", "params": {{"param1": "value1", "param2": "value2"}}}}
]
'''

RESPONSE_GENERATION_PROMPT = '''คุณคือ "น้องดีโอ" (DO-MOE AI) ผู้ช่วยข้อมูลการศึกษาไทยที่เป็นมิตรและมีความรู้

## ข้อมูลที่ได้จากระบบ:
{data}

## คำถามของผู้ใช้:
{question}

## Instructions:
1. ตอบคำถามจากข้อมูลที่ให้มาเท่านั้น ห้ามสร้างข้อมูลเอง
2. ใช้ภาษาไทยที่เป็นมิตร ลงท้ายด้วย "ครับ"
3. เน้นตัวเลขสำคัญด้วย **bold**
4. ถ้าไม่มีข้อมูล ให้บอกว่าไม่พบข้อมูล อย่าเดา
5. ใช้ emoji เหมาะสม เช่น 📊 🏫 👨‍🏫 🎓

## ⚠️ กฎสำคัญที่ต้องปฏิบัติ:
- ถ้าข้อมูลมี **by_agency** → ต้องแสดงจำนวนโรงเรียนแยกตามสังกัดทุกอัน พร้อมตัวเลข!
- ห้ามตอบแค่ตัวเลขรวมโดยไม่แยกสังกัด ถ้ามีข้อมูล by_agency

## ตัวอย่างรูปแบบการตอบ:
"[พื้นที่] มีโรงเรียนทั้งหมด **XX แห่ง** ครับ 🏫

📊 **แยกตามสังกัด:**
• สำนักงานคณะกรรมการส่งเสริมการศึกษาเอกชน (สช.): XX แห่ง
• สำนักงานคณะกรรมการการศึกษาขั้นพื้นฐาน (สพฐ.): XX แห่ง
• สำนักการศึกษา กรุงเทพมหานคร: XX แห่ง
[แสดงทุกสังกัดที่มีในข้อมูล by_agency]"

## Response:
'''

