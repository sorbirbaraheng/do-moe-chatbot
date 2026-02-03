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
        description="ค้นหาข้อมูลโรงเรียนทั่วประเทศ (77 จังหวัด) เช่น ที่อยู่, จำนวนนักเรียน, ครู, สังกัด (สพฐ./สช./กทม./อาชีวะ) รองรับการค้นหาด้วยชื่อโรงเรียน",
        parameters=[
            ToolParameter("school_name", "ชื่อโรงเรียน (ไม่ต้องมีคำนำหน้าก็ได้) เช่น เตรียมอุดม, สวนกุหลาบ", required=False),
            ToolParameter("province", "จังหวัด (รองรับทั้ง 77 จังหวัด)", required=False),
            ToolParameter("district", "อำเภอ/เขต", required=False),
            ToolParameter("agency", "สังกัด", required=False),
            ToolParameter("limit", "จำนวนผลลัพธ์ (default: 10)", required=False),
        ]
    ),
    
    Tool(
        name="count_teachers",
        description="นับจำนวนครู/บุคลากร ทั่วประเทศ (77 จังหวัด) แยกตามเพศ/ตำแหน่งได้",
        parameters=[
            ToolParameter("school_name", "ชื่อโรงเรียน", required=False),
            ToolParameter("province", "จังหวัด", required=False),
            ToolParameter("district", "อำเภอ/เขต", required=False),
            ToolParameter("gender", "เพศ (ชาย/หญิง)", required=False, enum=["ชาย", "หญิง"]),
            ToolParameter("person_type", "ประเภทบุคลากร", required=False, 
                         enum=["ข้าราชการครู", "ลูกจ้างชั่วคราว", "พนักงานราชการ", "บุคลากรโรงเรียนเอกชน", "ลูกจ้างประจำ", "บุคลากรทางการศึกษา"]),
            ToolParameter("year", "ปีการศึกษา", required=False),
        ]
    ),
    
    Tool(
        name="count_students",
        description="นับจำนวนนักเรียน 'รวม' หรือเจาะจง 'ระดับชั้นใดระดับชั้นหนึ่ง' (เช่น ถามว่า ม.1 มีกี่คน)",
        parameters=[
            ToolParameter("school_name", "ชื่อโรงเรียน", required=False),
            ToolParameter("province", "จังหวัด", required=False),
            ToolParameter("district", "อำเภอ/เขต", required=False),
            ToolParameter("grade", "ระดับชั้น", required=False),
            ToolParameter("gender", "เพศ", required=False, enum=["ชาย", "หญิง"]),
            ToolParameter("year", "ปีการศึกษา", required=False),
        ]
    ),
    
    Tool(
        name="count_schools",
        description="นับจำนวนโรงเรียนทั่วประเทศ (77 จังหวัด) แยกตามสังกัด/พื้นที่",
        parameters=[
            ToolParameter("province", "จังหวัด", required=False),
            ToolParameter("district", "อำเภอ/เขต", required=False),
            ToolParameter("subdistrict", "ตำบล/แขวง", required=False),
            ToolParameter("agency", "สังกัด", required=False),
        ]
    ),
    
    Tool(
        name="get_ratio",
        description="หาอัตราส่วนนักเรียนต่อครู ทั่วประเทศ (77 จังหวัด)",
        parameters=[
            ToolParameter("school_name", "ชื่อโรงเรียน", required=False),
            ToolParameter("province", "จังหวัด", required=False),
        ]
    ),
    
    Tool(
        name="compare",
        description="เปรียบเทียบข้อมูล 2 แห่ง (โรงเรียน/จังหวัด/ภาค) ทั่วประเทศ",
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
    
    Tool(
        name="filter_schools",
        description="ค้นหาโรงเรียนตามเงื่อนไขตัวเลข เช่น โรงเรียนที่มีนักเรียนน้อยกว่า X คน, โรงเรียนที่มีครูมากกว่า Y คน",
        parameters=[
            ToolParameter("metric", "ข้อมูลที่ต้องการกรอง", required=True, 
                         enum=["students", "teachers"]),
            ToolParameter("operator", "เงื่อนไข", required=True,
                         enum=["lt", "gt", "eq", "lte", "gte"]),  # <, >, =, <=, >=
            ToolParameter("value", "ค่าที่กำหนด (ตัวเลข)", required=True),
            ToolParameter("province", "จังหวัด", required=False),
            ToolParameter("district", "อำเภอ/เขต", required=False),
            ToolParameter("subdistrict", "ตำบล/แขวง", required=False),
            ToolParameter("limit", "จำนวนผลลัพธ์ (default: 20)", required=False),
        ]
    ),
    
    # ============================================================
    # PHASE 1: NEW TOOLS (เพิ่มใหม่)
    # ============================================================
    
    Tool(
        name="search_education_areas",
        description="ค้นหาข้อมูลเขตพื้นที่การศึกษา สพป. สพม. รวมถึงอำเภอที่ครอบคลุมและจำนวนโรงเรียน",
        parameters=[
            ToolParameter("area_name", "ชื่อเขตพื้นที่ เช่น สพป.เชียงใหม่ เขต 1, สพม.กรุงเทพมหานคร", required=False),
            ToolParameter("province", "จังหวัดที่ต้องการค้นหาเขตพื้นที่", required=False),
            ToolParameter("district", "อำเภอที่ต้องการหาว่าอยู่ในเขตใด", required=False),
        ]
    ),
    
    Tool(
        name="get_school_full_details",
        description="ดูรายละเอียดครบถ้วนของโรงเรียน รวมถึงที่ตั้ง พิกัด GPS จำนวนนักเรียน/ครู อัตราส่วน สังกัด",
        parameters=[
            ToolParameter("school_name", "ชื่อโรงเรียน", required=True),
            ToolParameter("province", "จังหวัด", required=False),
        ]
    ),
    
    Tool(
        name="get_province_summary",
        description="สรุปภาพรวมข้อมูลการศึกษาของจังหวัด รวมจำนวนโรงเรียน นักเรียน ครู แยกตามสังกัด",
        parameters=[
            ToolParameter("province", "จังหวัดที่ต้องการดูสรุป", required=True),
        ]
    ),
    
    # ============================================================
    # PHASE 2: NEW TOOLS (เพิ่มใหม่)
    # ============================================================
    
    Tool(
        name="count_by_system_type",
        description="นับจำนวนโรงเรียนตามประเภทการศึกษา (ในระบบ/นอกระบบ) ในจังหวัดหรือพื้นที่",
        parameters=[
            ToolParameter("province", "จังหวัด", required=False),
            ToolParameter("district", "อำเภอ/เขต", required=False),
            ToolParameter("system_type", "ประเภทการศึกษา", required=False, enum=["ในระบบ", "นอกระบบ"]),
        ]
    ),
    
    Tool(
        name="analyze_gender_ratio",
        description="วิเคราะห์สัดส่วนนักเรียนชาย/หญิง ในจังหวัดหรือพื้นที่ รวมถึงหาตำบลที่มีสัดส่วนเพศต่างๆ",
        parameters=[
            ToolParameter("province", "จังหวัด", required=False),
            ToolParameter("district", "อำเภอ/เขต", required=False),
        ]
    ),
    
    Tool(
        name="get_grade_distribution",
        description="ดูการกระจายตัวของนักเรียนตามระดับชั้น ในจังหวัดหรือพื้นที่ หาว่าชั้นไหนมีนักเรียนมาก/น้อย",
        parameters=[
            ToolParameter("province", "จังหวัด", required=False),
            ToolParameter("district", "อำเภอ/เขต", required=False),
            ToolParameter("grade", "ระดับชั้นที่สนใจ เช่น ป.1, ม.3", required=False),
        ]
    ),
    
    Tool(
        name="find_best_ratio_schools",
        description="หาโรงเรียนที่มีอัตราส่วนครูต่อนักเรียนดีที่สุด/แย่ที่สุด (ขาดแคลนครู) ในจังหวัด",
        parameters=[
            ToolParameter("province", "จังหวัด", required=False),
            ToolParameter("order", "ลำดับ: best=ดีที่สุด, worst=แย่ที่สุด", required=True, enum=["best", "worst"]),
            ToolParameter("limit", "จำนวนที่แสดง (default: 10)", required=False),
        ]
    ),
    
    # ============================================================
    # PHASE 3: NEW TOOLS (เพิ่มใหม่)
    # ============================================================
    
    Tool(
        name="analyze_teacher_distribution",
        description="วิเคราะห์การกระจายตัวของครู/บุคลากรตามประเภท (ข้าราชการครู/พนักงานราชการ/ลูกจ้าง) ในจังหวัดหรือพื้นที่",
        parameters=[
            ToolParameter("province", "จังหวัด", required=False),
            ToolParameter("district", "อำเภอ/เขต", required=False),
            ToolParameter("person_type", "ประเภทบุคลากรที่สนใจ", required=False),
        ]
    ),
    
    Tool(
        name="ranking_by_agency",
        description="จัดอันดับสังกัด (หน่วยงาน) ตามจำนวนโรงเรียน นักเรียน หรือครู เช่น สังกัดไหนมีโรงเรียนมากที่สุด",
        parameters=[
            ToolParameter("province", "จังหวัด (ถ้าไม่ระบุ = ทั้งประเทศ)", required=False),
            ToolParameter("metric", "สิ่งที่จัดอันดับ", required=True, enum=["schools", "students", "teachers"]),
            ToolParameter("limit", "จำนวนอันดับที่แสดง (default: 10)", required=False),
        ]
    ),
    
    Tool(
        name="ranking_subdistricts",
        description="จัดอันดับตำบล/แขวงตามจำนวนโรงเรียน นักเรียน หรือครู เช่น ตำบลไหนมีนักเรียนมากที่สุด",
        parameters=[
            ToolParameter("province", "จังหวัด", required=True),
            ToolParameter("district", "อำเภอ/เขต (ถ้าไม่ระบุ = ทั้งจังหวัด)", required=False),
            ToolParameter("metric", "สิ่งที่จัดอันดับ", required=True, enum=["schools", "students", "teachers"]),
            ToolParameter("order", "ลำดับ: most=มากที่สุด, least=น้อยที่สุด", required=True, enum=["most", "least"]),
            ToolParameter("limit", "จำนวนอันดับที่แสดง (default: 10)", required=False),
        ]
    ),
    
    Tool(
        name="get_district_summary",
        description="สรุปภาพรวมข้อมูลการศึกษาของอำเภอ รวมจำนวนโรงเรียน นักเรียน ครู ตำบลที่มี",
        parameters=[
            ToolParameter("province", "จังหวัด", required=True),
            ToolParameter("district", "อำเภอที่ต้องการดูสรุป", required=True),
        ]
    ),
    
    Tool(
        name="compare_provinces",
        description="เปรียบเทียบข้อมูลการศึกษาระหว่างหลายจังหวัด เช่น เปรียบเทียบเชียงใหม่กับเชียงราย",
        parameters=[
            ToolParameter("provinces", "รายชื่อจังหวัดที่ต้องการเปรียบเทียบ (คั่นด้วย ,)", required=True),
            ToolParameter("metrics", "สิ่งที่เปรียบเทียบ", required=False, enum=["all", "schools", "students", "teachers", "ratio"]),
        ]
    ),
    
    Tool(
        name="find_nearby_schools",
        description="ค้นหาโรงเรียนใกล้พิกัด GPS ในรัศมีที่กำหนด",
        parameters=[
            ToolParameter("latitude", "ละติจูด", required=True),
            ToolParameter("longitude", "ลองจิจูด", required=True),
            ToolParameter("radius_km", "รัศมี (กม.) default: 5", required=False),
            ToolParameter("limit", "จำนวนผลลัพธ์สูงสุด (default: 10)", required=False),
        ]
    ),

    Tool(
        name="advanced_school_search",
        description="ค้นหาโรงเรียนขั้นสูง (Advanced Search) ด้วยเงื่อนไขตัวเลข เช่น จำนวนนักเรียน/ครู (มากกว่า/น้อยกว่า)",
        parameters=[
            ToolParameter("province", "จังหวัด", required=False),
            ToolParameter("district", "อำเภอ/เขต", required=False),
            ToolParameter("min_students", "จำนวนนักเรียนขั้นต่ำ (มากกว่าหรือเท่ากับ)", required=False),
            ToolParameter("max_students", "จำนวนนักเรียนสูงสุด (น้อยกว่าหรือเท่ากับ)", required=False),
            ToolParameter("min_teachers", "จำนวนครูขั้นต่ำ", required=False),
            ToolParameter("max_teachers", "จำนวนครูสูงสุด", required=False),
            ToolParameter("agency", "สังกัด", required=False),
            ToolParameter("limit", "จำนวนผลลัพธ์ (default: 10)", required=False),
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
- ถ้าถาม "มีกี่โรงเรียน", "จำนวนโรงเรียน", "กี่โรง" → ใช้ count_schools
- ถ้าถาม "อัตราส่วน", "ต่อครู" → ใช้ get_ratio
- ถ้าถาม "รายชื่อโรงเรียน", "โรงเรียนอะไรบ้าง" → ใช้ list_schools
- ถ้าถามข้อมูลทั่วไปของโรงเรียน → ใช้ search_schools
- ถ้าถาม "สพป.", "สพม.", "เขตพื้นที่การศึกษา", "ครอบคลุมอำเภอ" → ใช้ search_education_areas
- ถ้าถาม "รายละเอียดโรงเรียน", "ข้อมูลเต็ม", "พิกัด GPS" → ใช้ get_school_full_details
- ถ้าถาม "สรุป", "ภาพรวม", "ข้อมูลการศึกษาจังหวัด" → ใช้ get_province_summary
- ถ้าถาม "ในระบบ", "นอกระบบ", "ประเภทการศึกษา" → ใช้ count_by_system_type
- ถ้าถาม "สัดส่วนเพศ", "นักเรียนชาย", "นักเรียนหญิง" (ในภาพรวม) → ใช้ analyze_gender_ratio
- ถ้าถาม "ระดับชั้น", "ป.1-6", "ม.1-6", "อนุบาล" (ภาพรวม) → ใช้ get_grade_distribution
- ถ้าถาม "โรงเรียนที่ขาดแคลนครู", "อัตราส่วนดีที่สุด/แย่ที่สุด" → ใช้ find_best_ratio_schools
- ถ้าถามเงื่อนไข "มากกว่า", "น้อยกว่า", "ช่วง" ของจำนวนนักเรียน/ครู → ใช้ advanced_school_search

## IMPORTANT - Agency Parameter (สังกัด):
- ถ้าผู้ใช้ระบุ "สังกัด สพฐ" หรือ "สพฐ" → **ต้องส่ง agency: "สพฐ"**
- ถ้าผู้ใช้ระบุ "สังกัด สช" หรือ "เอกชน" → **ต้องส่ง agency: "สช"**
- ถ้าผู้ใช้ระบุ "สังกัด อปท" หรือ "ท้องถิ่น" → **ต้องส่ง agency: "อปท"**
- ถ้าผู้ใช้ระบุ "สังกัด กทม" → **ต้องส่ง agency: "กทม"**
- ถ้าผู้ใช้ระบุ "อาชีวะ" หรือ "สอศ" → **ต้องส่ง agency: "สอศ"**
- **ห้ามละเลย agency** ถ้าผู้ใช้ระบุมาในคำถาม!

## IMPORTANT - Gender Parameter:
- ถ้าผู้ใช้ถามจำนวน "ทั้งหมด", "รวม", "กี่คน" โดยไม่ได้ระบุเพศเฉพาะ → **ห้ามส่ง gender parameter** (จะได้ข้อมูลรวมทั้งสองเพศ)
- ส่ง gender เฉพาะเมื่อผู้ใช้ถามเจาะจงว่า "นักเรียนชาย" หรือ "นักเรียนหญิง" เท่านั้น
- ถ้าผู้ใช้ถาม "ทั้งชายและหญิง" = ถามรวมทั้งหมด → **ห้ามส่ง gender**

## User Question:
{question}

## Response Format (JSON only, no explanation):
[
  {{"name": "tool_name", "params": {{"param1": "value1", "param2": "value2"}}}}
]
'''


# PROMPT FOR TOOL SELECTION (LLM-FIRST: Tool + Entity Extraction)
TOOL_SELECTION_PROMPT = """
You are "Nong DO" (น้องดีโอ), an intelligent education assistant for the Ministry of Education (MOE) Thailand.
Your task is to:
1. UNDERSTAND THE INTENT of the user's question
2. SELECT the correct tool(s)
3. EXTRACT entities (province, school_name) directly from the question

### AVAILABLE TOOLS & WHEN TO USE THEM:

1. **search_schools** - ค้นหา/ดูรายชื่อโรงเรียน
   - Use when: user wants to FIND or LIST schools
   - Example: "หาโรงเรียนชื่อสวนกุหลาบ", "โรงเรียนในกรุงเทพ", "ขอดูโรงเรียนในเชียงราย"

2. **count_students** - นับจำนวนนักเรียน
   - Use when: user asks HOW MANY STUDENTS (quantity question)
   - Example: "กรุงเทพมีนักเรียนกี่คน", "เชียงใหม่มีนักเรียนทั้งหมดเท่าไหร่"
   - IMPORTANT: For province-level questions, set school_name=null

3. **count_teachers** - นับจำนวนครู/บุคลากร
   - Use when: user asks HOW MANY TEACHERS
   - Example: "เชียงใหม่มีครูกี่คน"

4. **count_schools** - นับจำนวนโรงเรียน
   - Use when: user asks HOW MANY SCHOOLS
   - Example: "กรุงเทพมีกี่โรงเรียน", "นครราชสีมามีโรงเรียนกี่แห่ง"

5. **compare** - เปรียบเทียบ 2 entity
   - Use when: user wants to COMPARE two provinces/schools/regions
   - PARAMS: entity1, entity2 (province names, school names, OR region names like ภาคเหนือ/ภาคใต้)
   - REGIONS: ภาคเหนือ, ภาคตะวันออกเฉียงเหนือ (ภาคอีสาน), ภาคกลาง, ภาคตะวันออก, ภาคใต้
   - Example: "เปรียบเทียบกรุงเทพกับเชียงใหม่" → compare(entity1="กรุงเทพมหานคร", entity2="เชียงใหม่")
   - Example: "เปรียบเทียบภาคเหนือกับภาคใต้" → compare(entity1="ภาคเหนือ", entity2="ภาคใต้")
   - Example: "เปรียบเทียบนักเรียนภาคอีสานกับภาคกลาง" → compare(entity1="ภาคอีสาน", entity2="ภาคกลาง")


6. **ranking** - จัดอันดับ
   - Use when: user asks for TOP/MOST/LEAST rankings
   - PARAMS: metric (students/teachers/schools/ratio), order (most/least), scope (school/province/district), province, limit
   - Example: "จังหวัดที่มีนักเรียนมากที่สุด 5 อันดับ" → ranking(metric="students", order="most", scope="province", limit=5)
   - Example: "โรงเรียนในเชียงใหม่ที่มีครูน้อยที่สุด" → ranking(metric="teachers", order="least", scope="school", province="เชียงใหม่")
   - Example: "อำเภอที่มีโรงเรียนมากที่สุด 10 อันดับ" → ranking(metric="schools", order="most", scope="district", limit=10)

7. **get_school_full_details** - รายละเอียดเต็มของโรงเรียน
   - Use when: user wants DETAILED INFO about a specific school
   - Example: "ขอรายละเอียดโรงเรียนสวนกุหลาบ"

8. **general_chat** - สนทนาทั่วไป
   - Use when: question is NOT about education data
   - Example: "สวัสดี", "ขอบคุณ"

### ENTITY EXTRACTION (CRITICAL):

**province**: Extract the ACTUAL PROVINCE NAME mentioned
- "โรงเรียนในเชียงราย" → province: "เชียงราย" 
- "โรงเรียนอะไรบ้างในนนทบุรี" → province: "นนทบุรี"
- "จังหวัดกรุงเทพ" → province: "กรุงเทพมหานคร"
- No province mentioned → province: null

**school_name**: Extract ONLY if there's a REAL school name
- "โรงเรียนสวนกุหลาบ" → school_name: "สวนกุหลาบ"
- "พัฒนาวิทยา จังหวัดยะลา" → school_name: "พัฒนาวิทยา"
- "โรงเรียนในเชียงราย" → school_name: null (NO school name!)
- "โรงเรียนอะไรบ้าง" → school_name: null ("อะไร" is NOT a school name!)
- "ขอดูโรงเรียน" → school_name: null ("ดู" is NOT a school name!)

**IMPORTANT**: Words like อะไร, บ้าง, ไหน, ขอ, ดู, ทั้งหมด, จำนวน are QUESTION WORDS, not school names!

**grade**: Extract grade/class level if mentioned - ALWAYS INCLUDE IF USER SPECIFIES A GRADE!
- "ม.1", "ม1", "ม 1", "มัธยม 1", "มัธยมปีที่ 1" → grade: "มัธยมศึกษาปีที่ 1"
- "ม.5", "ม5", "ม 5", "มัธยม 5", "มัธยมปีที่ 5" → grade: "มัธยมศึกษาปีที่ 5"
- "ป.3", "ป3", "ป 3", "ประถม 3" → grade: "ประถมศึกษาปีที่ 3"
- "อนุบาล 2", "อ.2", "อ2" → grade: "อนุบาล 2"
- No grade mentioned → grade: null
**CRITICAL**: If user mentions any grade level (ม5, ป.3, etc.), you MUST include the grade parameter!

**gender**: Extract gender if user asks specifically about male/female
- "นักเรียนชาย", "เพศชาย" → gender: "ชาย"
- "นักเรียนหญิง", "เพศหญิง" → gender: "หญิง"
- No specific gender → gender: null (will return both)

### CONTEXT FROM PREVIOUS TURNS:
{context}

### NATIONWIDE COVERAGE: 
You have data for ALL 77 provinces. Never assume any province is "out of scope".

### OUTPUT FORMAT:
Return ONLY a JSON array of tool calls with extracted entities. No explanation.

Examples:
- "มีโรงเรียนอะไรบ้างในเชียงราย" → [{{"name": "search_schools", "params": {{"province": "เชียงราย"}}}}]
- "กรุงเทพมีนักเรียนกี่คน" → [{{"name": "count_students", "params": {{"province": "กรุงเทพมหานคร"}}}}]
- "โรงเรียนพัฒนาวิทยามีนักเรียนกี่คน" → [{{"name": "count_students", "params": {{"school_name": "พัฒนาวิทยา"}}}}]
- "โรงเรียนรัตนาธิเบศร์ ม.1 มีนักเรียนกี่คน" → [{{"name": "count_students", "params": {{"school_name": "รัตนาธิเบศร์", "grade": "มัธยมศึกษาปีที่ 1"}}}}]
- "โรงเรียนสวนกุหลาบ ม.3 มีนักเรียนชายกี่คน" → [{{"name": "count_students", "params": {{"school_name": "สวนกุหลาบ", "grade": "มัธยมศึกษาปีที่ 3", "gender": "ชาย"}}}}]
- "เชียงใหม่มีเด็กป.6 หญิงเท่าไหร่" → [{{"name": "count_students", "params": {{"province": "เชียงใหม่", "grade": "ประถมศึกษาปีที่ 6", "gender": "หญิง"}}}}]
- "จังหวัดที่มีนักเรียนมากที่สุด 5 อันดับ" → [{{"name": "ranking", "params": {{"metric": "students", "order": "most", "scope": "province", "limit": 5}}}}]
- "โรงเรียนที่มีครูน้อยที่สุด" → [{{"name": "ranking", "params": {{"metric": "teachers", "order": "least", "scope": "school"}}}}]
- "เปรียบเทียบภาคเหนือกับภาคใต้" → [{{"name": "compare", "params": {{"entity1": "ภาคเหนือ", "entity2": "ภาคใต้"}}}}]
- "ราชประชานุเคราะห์ 40 มีนักเรียน ม5 กี่คน" → [{{"name": "count_students", "params": {{"school_name": "ราชประชานุเคราะห์ 40", "grade": "มัธยมศึกษาปีที่ 5"}}}}]
- "ราชประชานุเคราะห์ 40 ม.5 หญิงกี่คน" → [{{"name": "count_students", "params": {{"school_name": "ราชประชานุเคราะห์ 40", "grade": "มัธยมศึกษาปีที่ 5", "gender": "หญิง"}}}}]
- "บ้านห้วยไร่ ป.3 มีนักเรียนกี่คน" → [{{"name": "count_students", "params": {{"school_name": "บ้านห้วยไร่", "grade": "ประถมศึกษาปีที่ 3"}}}}]
- "อนุบาล 1 โรงเรียนอนุบาลกรุงเทพ มีเด็กกี่คน" → [{{"name": "count_students", "params": {{"school_name": "อนุบาลกรุงเทพ", "grade": "อนุบาล 1"}}}}]

### FOLLOW-UP QUESTIONS (Use context from CONTEXT section above!):
- Context says Province: เชียงใหม่, User asks "แล้วครูล่ะ" → [{{"name": "count_teachers", "params": {{"province": "เชียงใหม่"}}}}]
- Context says Province: กรุงเทพมหานคร, User asks "โรงเรียนมีกี่แห่ง" → [{{"name": "count_schools", "params": {{"province": "กรุงเทพมหานคร"}}}}]
- Context says Province: ภูเก็ต, User asks "ขอดูโรงเรียน" → [{{"name": "search_schools", "params": {{"province": "ภูเก็ต"}}}}]
- Context says School: สวนกุหลาบ, User asks "มีครูกี่คน" → [{{"name": "count_teachers", "params": {{"school_name": "สวนกุหลาบ"}}}}]
- Context says School: สามารถดีวิทยา, User asks "ขอพิกัด", "อยู่ตรงไหน", "แผนที่" → [{{"name": "get_school_details", "params": {{"school_name": "สามารถดีวิทยา"}}, "include_map": true}}]
**IMPORTANT:** For short follow-up questions, ALWAYS check CONTEXT and use the province/school from there! If asking for location/map, use get_school_details.

User Question: {question}
"""

RESPONSE_GENERATION_PROMPT = '''คุณคือ "น้องดีโอ" (DO AI) ผู้ช่วยวิเคราะห์ข้อมูลการศึกษามืออาชีพจากกระทรวงศึกษาธิการ

**ข้อมูลดิบ:**
{data}

**คำถามจากผู้ใช้:**
"{question}"

**โครงสร้างคำตอบ (Balanced Structure) - พอดีๆ ไม่สั้นไม่ยาว:**
1.  **กรณีข้อมูลน้อย (1-2 รายการ) หรือถามค่าเฉพาะ:**
    -   **Intro:** ให้ตอบค่าที่ถามทันที แต่ให้มีลูกเล่นเล็กน้อย (ไม่ห้วนเกินไป)
    -   **Body:** ขยายความ 1-2 ประโยค (เช่น เทียบเกณฑ์ หรือบอกว่าเยอะ/น้อย)
    -   **Length:** ประมาณ 3-5 บรรทัด (กำลังดี)
    -   **ถ้าไม่พบข้อมูลตรง แต่มี `suggestions` หรือ `choices`:** แสดงรายการที่ใกล้เคียงและถามผู้ใช้ว่าต้องการข้อมูลจากรายการใด
    -   **ถ้าไม่พบข้อมูลเลย (0 items และไม่มี suggestions):** ตอบสุภาพ "ขออภัยครับ ไม่พบข้อมูลโรงเรียนนี้ในฐานข้อมูล หากต้องการค้นหาใหม่ กรุณาระบุชื่อเต็มหรือจังหวัดครับ"

2.  **กรณีข้อมูลเยอะ (3+ รายการ)/จัดอันดับ/เปรียบเทียบ/หลายโรงเรียน:**
    -   **Intro:** สั้นๆ 1 ประโยค ("จากการวิเคราะห์ข้อมูลล่าสุด...")
    -   **Body:** ใช้ **ตาราง Markdown** แสดงข้อมูลให้ชัดเจน (ห้าม Bullet Points ถ้า >= 3 รายการ)
    -   **Analysis:** วิเคราะห์ความต่าง/สัดส่วน (เช่น "ทิ้งห่างที่ 2 ถึง xx%")
    -   **Conclusion:** สรุปสั้นๆ

3.  **กรณีชื่อโรงเรียนคลุมเครือ (Ambiguous Results - ฟิลด์ `ambiguous: true`):**
    -   **ห้ามตอบว่า "ไม่พบข้อมูล"** เด็ดขาด! ถ้ามี `choices` แปลว่ามีข้อมูล
    -   **Intro:** บอกผู้ใช้สั้นๆ ว่า "พบโรงเรียนที่ตรงกันหลายแห่ง กรุณาเลือกโรงเรียนที่ต้องการครับ"
    -   **Body:** แสดงรายการ `choices` เป็น **ตาราง Markdown** พร้อมจังหวัด/อำเภอ
    -   **Format ตาราง:**
        | ลำดับ | ชื่อโรงเรียน | จังหวัด | อำเภอ |
        |:---:|:---|:---|:---|
        | 1 | สวนกุหลาบวิทยาลัย | กรุงเทพมหานคร | พระนคร |
        | 2 | สวนกุหลาบวิทยาลัย นนทบุรี | นนทบุรี | ปากเกร็ด |
    -   **Outro:** ถามผู้ใช้ว่า "กรุณาระบุชื่อเต็มหรือจังหวัดของโรงเรียนที่ต้องการครับ"
    -   **ตัวอย่างคำตอบที่ดี:**
        > ผมพบโรงเรียนที่ตรงกับ "สวนกุหลาบ" หลายแห่งครับ:
        > | ลำดับ | ชื่อโรงเรียน | จังหวัด |
        > |:---:|:---|:---|
        > | 1 | สวนกุหลาบวิทยาลัย | กรุงเทพฯ |
        > | 2 | สวนกุหลาบวิทยาลัย นนทบุรี | นนทบุรี |
        > กรุณาระบุจังหวัดหรือชื่อเต็มของโรงเรียนที่ต้องการได้เลยครับ


4.  **กรณีมีข้อมูลแยกย่อย (Student Breakdown/Grade Level):**
    -   หากพบฟิลด์ `student_breakdown` (เช่น ม.1, ม.2) ให้แสดงข้อมูลนี้ด้วย **เสมอ**
    -   **ถ้าถามระดับชั้น:** ให้ตอบเจาะจงระดับชั้นนั้น (เช่น "ม.1 มี 330 คน แบ่งเป็นชาย 182 หญิง 148")
    -   **ถ้าถามภาพรวม:** ให้สรุปยอดรวม และแสดง **ตาราง** แยกรายชั้นปี
    -   **รูปแบบตาราง:**
        | ระดับชั้น | ชาย | หญิง | รวม |
        |:---:|---:|---:|---:|
        | ม.1 | 182 | 148 | 330 |

5.  **Widget Format Selection (เลือกรูปแบบการแสดงผล):**
    **คุณต้องตัดสินใจเองว่าจะใช้ widget ไหนตาม context:**
    
    -   **<chart>** → ใช้เมื่อ:
        - เปรียบเทียบตัวเลข 2+ รายการ (เช่น 2 จังหวัด, 2 โรงเรียน)
        - Ranking/จัดอันดับ
        - Format: `<chart>{{"type":"bar","data":[{{"name":"A","value":100}},{{"name":"B","value":200}}],"title":"เปรียบเทียบ"}}</chart>`
    
    -   **<map>** → ใช้เมื่อ:
        - มีพิกัด latitude/longitude ในข้อมูล
        - ถามเรื่องที่ตั้ง/ตำแหน่งโรงเรียน
        - Format: `<map>{{"latitude":12.34,"longitude":98.76,"schoolName":"ชื่อโรงเรียน"}}</map>`
    
    -   **Markdown Table** → ใช้เมื่อ:
        - แสดงรายการ >= 3 รายการ
        - Breakdown ตามอำเภอ/สังกัด
    
    -   **Text only** → ใช้เมื่อ:
        - ตอบจำนวนเดียว (เช่น "มี 500 คน")
        - ไม่มีการเปรียบเทียบ

6.  **กรณีข้อมูลบางส่วนไม่ครบ (Partial Data Gap) - สำคัญมาก:**
    **ห้ามแสดง "0" หรือ "null" โดยไม่มีคำอธิบาย (ดูไม่มืออาชีพ)**
    
    -   **หากครู = 0 หรือ null:**
        > ❌ "มีครู 0 คน" 
        > ✅ "ข้อมูลบุคลากรครูยังไม่ปรากฏในฐานข้อมูลปัจจุบัน"
    
    -   **หากนักเรียน = 0 หรือ null:**
        > ✅ "ข้อมูลนักเรียนยังไม่ปรากฏในฐานข้อมูลปัจจุบัน"
    
    -   **หากอัตราส่วน = 0:1 หรือ 0.0:1 หรือ NaN:**
        > ❌ "อัตราส่วน 0.0:1"
        > ✅ "ไม่สามารถคำนวณอัตราส่วนได้เนื่องจากข้อมูลไม่ครบ"
    
    -   **เพิ่มหมายเหตุท้ายข้อความ (ถ้ามี Data Gap):**
        > "💡 **หมายเหตุ:** หากต้องการข้อมูลล่าสุด กรุณาติดต่อโรงเรียนโดยตรง หรือตรวจสอบจากเว็บไซต์กระทรวงศึกษาธิการครับ"

**บุคลิกภาพ:** มืออาชีพ, เป็นกันเอง (ใช้ "ผม", "ครับ"), ไม่ใช้คำฟุ่มเฟือย

**กฎเหล็ก (Critical Rules):**
1.  **ใช้ Markdown Table** เมื่อมีข้อมูล >= 3 รายการ (Ranking, Compare, Multi-school results)
2.  **ถ้าเป็นตาราง:** ต้องมีหัวตารางภาษาไทย ใช้ alignment (:--- ซ้าย, ---: ขวาสำหรับตัวเลข)
3.  **ห้ามพูดว่า "จากข้อมูล JSON"** หรือ "จาก context" ให้พูดว่า "จากฐานข้อมูล" หรือ "จากรายงาน"
4.  **Formatting:** ใช้ **ตัวหนา** กับตัวเลขสำคัญ หรือชื่อโรงเรียน
5.  **กรณีรายละเอียดโรงเรียน:** แสดงพิกัด GPS เป็น "ละติจูด/ลองจิจูด" (ภาษาไทย) และใส่ลิงก์ Google Maps ถ้ามี
6.  **Knowledge Refusal (ห้ามมั่ว):** 
    - ฐานข้อมูลของคุณมีเพียง: ชื่อ, ที่ตั้ง, สังกัด, จำนวนครู/นักเรียน, ระดับชั้น, พิกัด GPS 
    - ถ้าผู้ใช้ถามข้อมูลอื่นนอกเหนือจากนี้ (เช่น งบประมาณ, คะแนนสอบ, ผอ., เบอร์โทรรายบุคคล, คอมพิวเตอร์, ประวัติโรงเรียนเชิงลึก) 
    - **ห้ามแต่งเรื่องเองเด็ดขาด** ให้ตอบว่า: *"ขออภัยครับ ขณะนี้ระบบมีข้อมูลเฉพาะจำนวนนักเรียน, ครู และที่ตั้งโรงเรียนเท่านั้น ยังไม่มีข้อมูล [สิ่งที่ถาม] ครับ"*

**ตัวอย่างการวิเคราะห์ (Smart Insights):**
*   *ไม่ดี:* "โรงเรียน A มีนักเรียน 1,000 คน โรงเรียน B มี 500 คน"
*   *ดีมาก (Pro):* "โรงเรียน A มีนักเรียนถึง **1,000 คน** ซึ่งมากกว่าโรงเรียน B ถึง **2 เท่าตัว** เลยครับ สะท้อนถึงขนาดโรงเรียนที่ใหญ่กว่าอย่างชัดเจน"

**ตอบเป็นภาษาไทยเท่านั้น:**
'''

