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
            ToolParameter("region", "ภาค (เช่น ภาคเหนือ, ภาคใต้)", required=False),
            ToolParameter("metric", "สิ่งที่ต้องการค้นหา (เพื่อกรองข้อมูล)", required=False, enum=["students", "teachers"]),
            ToolParameter("limit", "จำนวนผลลัพธ์ (default: 10)", required=False),
            ToolParameter("year", "ปีการศึกษา เช่น 2567", required=False),
        ]
    ),
    
    Tool(
        name="count_teachers",
        description="นับจำนวนครู/บุคลากร ทั่วประเทศ (77 จังหวัด) แยกตามเพศ/ตำแหน่งได้",
        parameters=[
            ToolParameter("school_name", "ชื่อโรงเรียน", required=False),
            ToolParameter("province", "จังหวัด", required=False),
            ToolParameter("region", "ภาค (เช่น ภาคเหนือ, ภาคใต้)", required=False),
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
            ToolParameter("region", "ภาค (เช่น ภาคเหนือ, ภาคใต้)", required=False),
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
            ToolParameter("region", "ภาค (เช่น ภาคเหนือ, ภาคใต้)", required=False),
            ToolParameter("agency", "สังกัด", required=False),
            ToolParameter("year", "ปีการศึกษา เช่น 2567", required=False),
        ]
    ),
    
    Tool(
        name="get_ratio",
        description="หาอัตราส่วนนักเรียนต่อครู ทั่วประเทศ (77 จังหวัด)",
        parameters=[
            ToolParameter("school_name", "ชื่อโรงเรียน", required=False),
            ToolParameter("province", "จังหวัด", required=False),
            ToolParameter("year", "ปีการศึกษา เช่น 2567", required=False),
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
            ToolParameter("year", "ปีการศึกษา เช่น 2567", required=False),
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
            ToolParameter("region", "ภาค (ถ้าต้องการจำกัดเฉพาะภาค)", required=False),
            ToolParameter("limit", "จำนวนอันดับที่แสดง (default: 5)", required=False),
            ToolParameter("year", "ปีการศึกษา เช่น 2567", required=False),
        ]
    ),
    
    Tool(
        name="list_schools",
        description="แสดงรายชื่อโรงเรียนในพื้นที่ พร้อมข้อมูลย่อ",
        parameters=[
            ToolParameter("province", "จังหวัด", required=False),
            ToolParameter("region", "ภาค (เช่น ภาคเหนือ, ภาคใต้)", required=False),
            ToolParameter("district", "อำเภอ/เขต", required=False),
            ToolParameter("agency", "สังกัด", required=False),
            ToolParameter("limit", "จำนวนที่แสดง (default: 10)", required=False),
            ToolParameter("year", "ปีการศึกษา เช่น 2567", required=False),
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
            ToolParameter("region", "ภาค (เช่น ภาคเหนือ, ภาคใต้)", required=False),
            ToolParameter("district", "อำเภอ/เขต", required=False),
            ToolParameter("subdistrict", "ตำบล/แขวง", required=False),
            ToolParameter("limit", "จำนวนผลลัพธ์ (default: 20)", required=False),
            ToolParameter("year", "ปีการศึกษา เช่น 2567", required=False),
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
        name="get_education_area_info",
        description="ดูข้อมูลเขตพื้นที่การศึกษา ว่าครอบคลุมอำเภอใดบ้าง มีโรงเรียนกี่แห่งในแต่ละอำเภอ ใช้เมื่อถาม 'สพป.เชียงใหม่ เขต 1 ครอบคลุมอำเภออะไรบ้าง'",
        parameters=[
            ToolParameter("area_name", "ชื่อเขตพื้นที่การศึกษา เช่น สพป.เชียงใหม่ เขต 1, สพม.เชียงใหม่", required=True),
        ]
    ),

    
    Tool(
        name="get_school_full_details",
        description="ดูรายละเอียดครบถ้วนของโรงเรียน รวมถึงที่ตั้ง พิกัด GPS จำนวนนักเรียน/ครู อัตราส่วน สังกัด",
        parameters=[
            ToolParameter("school_name", "ชื่อโรงเรียน", required=True),
            ToolParameter("province", "จังหวัด", required=False),
            ToolParameter("year", "ปีการศึกษา เช่น 2567", required=False),
        ]
    ),
    
    Tool(
        name="get_province_summary",
        description="สรุปภาพรวมข้อมูลการศึกษาของจังหวัด รวมจำนวนโรงเรียน นักเรียน ครู แยกตามสังกัด",
        parameters=[
            ToolParameter("province", "จังหวัดที่ต้องการดูสรุป", required=True),
            ToolParameter("year", "ปีการศึกษา เช่น 2567", required=False),
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
            ToolParameter("year", "ปีการศึกษา เช่น 2567", required=False),
        ]
    ),
    
    Tool(
        name="analyze_gender_ratio",
        description="วิเคราะห์สัดส่วนนักเรียนชาย/หญิง ในจังหวัดหรือพื้นที่ รวมถึงหาตำบลที่มีสัดส่วนเพศต่างๆ",
        parameters=[
            ToolParameter("province", "จังหวัด", required=False),
            ToolParameter("district", "อำเภอ/เขต", required=False),
            ToolParameter("year", "ปีการศึกษา เช่น 2567", required=False),
        ]
    ),
    
    Tool(
        name="get_grade_distribution",
        description="ดูการกระจายตัวของนักเรียนตามระดับชั้น ในจังหวัดหรือพื้นที่ หาว่าชั้นไหนมีนักเรียนมาก/น้อย",
        parameters=[
            ToolParameter("province", "จังหวัด", required=False),
            ToolParameter("district", "อำเภอ/เขต", required=False),
            ToolParameter("grade", "ระดับชั้นที่สนใจ เช่น ป.1, ม.3", required=False),
            ToolParameter("year", "ปีการศึกษา เช่น 2567", required=False),
        ]
    ),
    
    Tool(
        name="find_best_ratio_schools",
        description="หาโรงเรียนที่มีอัตราส่วนครูต่อนักเรียนดีที่สุด/แย่ที่สุด (ขาดแคลนครู) ในจังหวัด",
        parameters=[
            ToolParameter("province", "จังหวัด", required=False),
            ToolParameter("order", "ลำดับ: best=ดีที่สุด, worst=แย่ที่สุด", required=True, enum=["best", "worst"]),
            ToolParameter("limit", "จำนวนที่แสดง (default: 10)", required=False),
            ToolParameter("year", "ปีการศึกษา เช่น 2567", required=False),
        ]
    ),
    
    # ============================================================
    # PHASE 3: NEW TOOLS (เพิ่มใหม่)
    # ============================================================
    
    Tool(
        name="analyze_teacher_distribution",
        description="วิเคราะห์การกระจายตัวของครู/บุคลากรตามประเภท (ข้าราชการครู/พนักงานราชการ/ลูกจ้าง) ในจังหวัดหรือพื้นที่ สามารถกรองตามเพศได้",
        parameters=[
            ToolParameter("province", "จังหวัด", required=False),
            ToolParameter("district", "อำเภอ/เขต", required=False),
            ToolParameter("region", "ภูมิภาค เช่น ภาคใต้ ภาคเหนือ", required=False),
            ToolParameter("person_type", "ประเภทบุคลากรที่สนใจ", required=False),
            ToolParameter("gender", "เพศ: ชาย หรือ หญิง", required=False),
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
        name="compare_years",
        description="เปรียบเทียบข้อมูลการศึกษาระหว่าง 2 ปี เช่น เปรียบเทียบนักเรียนปี 67 กับ 68, ปีนี้กับปีที่แล้ว",
        parameters=[
            ToolParameter("year1", "ปีแรก เช่น 2567, 67", required=True),
            ToolParameter("year2", "ปีที่สอง เช่น 2568, 68", required=True),
            ToolParameter("province", "จังหวัด (ถ้าต้องการเจาะจง)", required=False),
            ToolParameter("school_name", "ชื่อโรงเรียน (ถ้าต้องการเจาะจง)", required=False),
            ToolParameter("metric", "ตัวชี้วัด", required=False, enum=["all", "students", "teachers", "schools", "ratio"]),
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
- ถ้าถาม "ครอบคลุมอำเภอ", "เขต X มีอำเภออะไรบ้าง", "สพป./สพม. ครอบคลุม" → ใช้ get_education_area_info
- ถ้าถาม "สพป.", "สพม.", "เขตพื้นที่การศึกษา" (ค้นหาเขต) → ใช้ search_education_areas
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
2. SELECT the correct tool(s) from the list below
3. EXTRACT entities (province, school_name, region, etc.) directly from the question

### COMPLETE TOOL CATALOG (ALL AVAILABLE TOOLS):

**📊 COUNTING TOOLS:**
| Tool | Use When | Required/Optional Params |
|------|----------|--------------------------|
| `count_schools` | นับจำนวนโรงเรียน | province, district, agency, region |
| `count_students` | นับจำนวนนักเรียน | province, district, school_name, gender, grade, **region** |
| `count_teachers` | นับจำนวนครู | province, district, school_name, gender, person_type, region |

**🔍 SEARCH & LIST TOOLS:**
| Tool | Use When | Required/Optional Params |
|------|----------|--------------------------|
| `search_schools` | ค้นหาโรงเรียนตามชื่อ/จังหวัด | school_name, province, district, agency |
| `list_schools` | แสดงรายชื่อโรงเรียน | province, district, agency, limit |
| `get_school_full_details` | รายละเอียดโรงเรียน (ที่อยู่, เบอร์, GPS) | **school_name (REQUIRED!)** |

**📈 ANALYSIS TOOLS:**
| Tool | Use When | Required/Optional Params |
|------|----------|--------------------------|
| `analyze_teacher_distribution` | วิเคราะห์โครงสร้างครู (แยกประเภท, เพศ) | province, district, region, person_type, gender |
| `get_grade_distribution` | วิเคราะห์นักเรียนแยกตามระดับชั้น | province, district, grade |
| `analyze_gender_ratio` | วิเคราะห์สัดส่วนชาย/หญิง | province, district |
| `get_ratio` | อัตราส่วนครู:นักเรียน | province, school_name |

**🏆 RANKING TOOLS:**
| Tool | Use When | Required/Optional Params |
|------|----------|--------------------------|
| `ranking` | จัดอันดับ (มากที่สุด/น้อยที่สุด) | metric, order, scope, province, **region**, limit |
| `ranking_by_agency` | จัดอันดับตามสังกัด | province, metric, limit |
| `ranking_subdistricts` | จัดอันดับตำบล | province, district, metric, order, limit |

**⚖️ COMPARISON TOOLS:**
| Tool | Use When | Required/Optional Params |
|------|----------|--------------------------|
| `compare` | เปรียบเทียบ 2 จังหวัด/ภาค | entity1, entity2, metric |
| `compare_provinces` | เปรียบเทียบหลายจังหวัด | provinces (comma-separated), metrics |
| `compare_years` | เปรียบเทียบ 2 ปี (ปี 67 vs 68) | year1, year2, province, school_name, metric |

**🔢 NUMERIC FILTER TOOLS (for > < = conditions):**
| Tool | Use When | Required/Optional Params |
|------|----------|--------------------------|
| `advanced_school_search` | ค้นหาโรงเรียนตามเงื่อนไขตัวเลข | min_students, max_students, min_teachers, max_teachers, province |
| `filter_schools` | กรองโรงเรียนด้วย operator | metric (students/teachers), operator (lt/gt/eq/lte/gte), value |

**🗺️ LOCATION & AREA TOOLS:**
| Tool | Use When | Required/Optional Params |
|------|----------|--------------------------|
| `search_education_areas` | ค้นหาเขตพื้นที่การศึกษา (สพป./สพม.) | province, area_name |
| `get_education_area_info` | ดูว่าเขตพื้นที่ครอบคลุมอำเภอใดบ้าง มีกี่โรงเรียน | area_name (REQUIRED!) |
| `find_nearby_schools` | หาโรงเรียนใกล้เคียงพิกัด GPS | latitude, longitude, radius_km |
| `get_province_summary` | สรุปภาพรวมจังหวัด | province |
| `get_district_summary` | สรุปภาพรวมอำเภอ | province, district |

**💬 GENERAL:**
| Tool | Use When | Required/Optional Params |
|------|----------|--------------------------|
| `general_chat` | คำถามทั่วไป ไม่เกี่ยวกับข้อมูลการศึกษา | (none) |

### ENTITY EXTRACTION RULES:

**province/region**: 
- ภาคเหนือ, ภาคใต้, ภาคอีสาน, ภาคกลาง, ภาคตะวันออก = REGION (use region parameter)
- กรุงเทพ, เชียงใหม่, ปัตตานี, etc. = PROVINCE

**CONCEPT GROUPS (must expand before calling tools):**
- "3 จังหวัดชายแดนภาคใต้" or "สามจังหวัดชายแดน" → use compare_provinces with provinces="ปัตตานี,ยะลา,นราธิวาส"
- "5 จังหวัดอีสานตอนบน" → use compare_provinces with individual provinces
- "EEC" or "อีอีซี" → provinces in ชลบุรี, ระยอง, ฉะเชิงเทรา

**school_name**: ⚠️ CRITICAL! ONLY extract if it is an ACTUAL, REAL school name!
- ❌ STOP WORDS - These are NEVER school names: "อะไร", "บ้าง", "ไหน", "ทั้งหมด", "ที่", "แต่ละ", "ชายแดน", "ขนาดเล็ก", "ขนาดใหญ่", "ดีที่สุด", "มากที่สุด", "น้อยที่สุด", "กี่", "เท่าไหร่", "เท่าไร", "รวม", "รวมกัน", "ทุก", "หมด", "ใด"
- ✅ Real school names: "สวนกุหลาบ", "อนุบาลปัตตานี", "เบญจมราชูทิศ", "พัฒนาวิทยา"
- ⚠️ If the question asks "จังหวัดไหน", "โรงเรียนไหน", "ที่ไหน" → these are QUESTION WORDS, NOT school names!
- ⚠️ If the question asks about "ชายแดน", "ขนาดเล็ก" → these are DESCRIPTORS, NOT school names!

**person_type** (for teacher queries):
- "ครูราชการ", "ข้าราชการ" → person_type: "ข้าราชการครู"
- "ครูอัตราจ้าง", "พนักงานราชการ" → person_type: "ลูกจ้างชั่วคราว"

**Numeric conditions** (triggers advanced_school_search or filter_schools):
- "น้อยกว่า 100 คน", "< 100" → max_students=100 OR operator="lt", value=100
- "มากกว่า 500 คน", "> 500" → min_students=500 OR operator="gt", value=500
- "ไม่ถึง 5 คน", "ไม่เกิน 5" → max_teachers=5

### INTENT DETECTION PRIORITY:
Before extracting entities, determine the INTENT first:
0. ⚠️ **YEAR COMPARISON (HIGHEST PRIORITY):** If the question mentions 2 different years (e.g. "ปี 67 กับ 68", "ปี 2567 vs 2568", "เปรียบเทียบปีนี้กับปีที่แล้ว", "ต่างกันกี่คน ปี X ปี Y") → ALWAYS use `compare_years` with year1 and year2. DO NOT use `compare`, `count_students`, or `count_teachers` for year comparisons!
1. "จังหวัดไหน/จังหวัดใด + มากที่สุด/ดีที่สุด" → `ranking` tool (NOT search_schools!)
2. "โรงเรียนที่มี...มากที่สุด/น้อยที่สุด" → `ranking` tool with scope="school"
3. "เปรียบเทียบ + school_A + กับ + school_B" → call `get_school_full_details` for EACH school
4. "ใน แต่ละ จังหวัด" → `ranking` tool with appropriate scope
5. "3 จังหวัดชายแดน" → `compare_provinces` with provinces="ปัตตานี,ยะลา,นราธิวาส"
6. "อัตราส่วนครูต่อนักเรียนดีที่สุด" → `ranking` with metric="ratio"
7. "จังหวัดไหน/อำเภอไหน/ตำบลไหน + ใน + [ภาค/จังหวัด] + มากที่สุด" → `ranking` with scope=province/district/subdistrict + region/province filter
8. "ภาคไหนมี...มากที่สุด" → `ranking` with scope="province" (ranks all provinces nationwide)

### ⚠️ YEAR COMPARISON RULES:
- If user mentions TWO years (e.g. "67", "68", "2567", "2568") → MUST use `compare_years`
- Keywords: "เปรียบเทียบ...ปี", "ต่างกัน", "เทียบปี", "ปี X กับ Y", "ปี X vs Y"
- metric mapping: "นักเรียน" → "students", "ครู" → "teachers", "โรงเรียน" → "schools"
- Available years: 2566 (66), 2567 (67) and 2568 (68)

### CONTEXT FROM PREVIOUS TURNS:
{context}

### OUTPUT FORMAT:
Return ONLY a JSON array. No explanation.

**EXAMPLES:**
- "โรงเรียนในปัตตานีมีกี่แห่ง" → [{{"name": "count_schools", "params": {{"province": "ปัตตานี"}}}}]
- "โรงเรียนและครูในปัตตานีมีทั้งหมดกี่คน" → [{{"name": "get_province_summary", "params": {{"province": "ปัตตานี"}}}}]
- "โรงเรียนในปัตตานีมีกี่แห่ง และมีครูเท่าไหร่" → [{{"name": "get_province_summary", "params": {{"province": "ปัตตานี"}}}}]
- "ครูในภาคใต้มีเท่าไหร่" → [{{"name": "count_teachers", "params": {{"region": "ภาคใต้"}}}}]
- "รายละเอียดครูภาคใต้" → [{{"name": "analyze_teacher_distribution", "params": {{"region": "ภาคใต้"}}}}]
- "ครูผู้ชายในปัตตานีมีกี่คน" → [{{"name": "analyze_teacher_distribution", "params": {{"province": "ปัตตานี", "gender": "ชาย"}}}}]
- "ปัตตานีมีครูผู้ชายหรือผู้หญิงมากกว่า" → [{{"name": "analyze_teacher_distribution", "params": {{"province": "ปัตตานี"}}}}]
- "นักเรียนในเชียงใหม่แยกตามชั้น" → [{{"name": "get_grade_distribution", "params": {{"province": "เชียงใหม่"}}}}]
- "โรงเรียนที่มีนักเรียนน้อยกว่า 100 คน" → [{{"name": "advanced_school_search", "params": {{"max_students": 100}}}}]
- "โรงเรียนขนาดเล็กที่มีครูไม่ถึง 5 คน" → [{{"name": "advanced_school_search", "params": {{"max_teachers": 5}}}}]
- "โรงเรียนในยะลาที่มีครูมากกว่า 50 คน" → [{{"name": "advanced_school_search", "params": {{"province": "ยะลา", "min_teachers": 50}}}}]
- "รายละเอียดโรงเรียนอนุบาลปัตตานี" → [{{"name": "get_school_full_details", "params": {{"school_name": "อนุบาลปัตตานี"}}}}]
- "เปรียบเทียบภาคเหนือกับภาคใต้" → [{{"name": "compare", "params": {{"entity1": "ภาคเหนือ", "entity2": "ภาคใต้"}}}}]
- "เปรียบเทียบโรงเรียนอนุบาลปัตตานีกับเบญจมราชูทิศ" → [{{"name": "get_school_full_details", "params": {{"school_name": "อนุบาลปัตตานี"}}}}, {{"name": "get_school_full_details", "params": {{"school_name": "เบญจมราชูทิศ"}}}}]
- "จังหวัดที่มีโรงเรียนมากที่สุด 5 อันดับ" → [{{"name": "ranking", "params": {{"metric": "schools", "order": "most", "scope": "province", "limit": 5}}}}]
- "จังหวัดไหนมีอัตราส่วนครูต่อนักเรียนดีที่สุด" → [{{"name": "ranking", "params": {{"metric": "ratio", "order": "least", "scope": "province", "limit": 10}}}}]
- "โรงเรียนที่มีนักเรียนมากที่สุดในแต่ละจังหวัด" → [{{"name": "ranking", "params": {{"metric": "students", "order": "most", "scope": "school", "limit": 10}}}}]
- "จังหวัดไหนในภาคกลางมีนักเรียนมากที่สุด" → [{{"name": "ranking", "params": {{"metric": "students", "order": "most", "scope": "province", "region": "ภาคกลาง", "limit": 5}}}}]
- "อำเภอไหนในเชียงใหม่มีโรงเรียนมากที่สุด" → [{{"name": "ranking", "params": {{"metric": "schools", "order": "most", "scope": "district", "province": "เชียงใหม่", "limit": 5}}}}]
- "ตำบลไหนในเชียงใหม่มีนักเรียนเยอะสุด" → [{{"name": "ranking", "params": {{"metric": "students", "order": "most", "scope": "subdistrict", "province": "เชียงใหม่", "limit": 5}}}}]
- "จังหวัดไหนในประเทศไทยมีครูมากที่สุด" → [{{"name": "ranking", "params": {{"metric": "teachers", "order": "most", "scope": "province", "limit": 10}}}}]
- "3 จังหวัดชายแดนภาคใต้มีนักเรียนรวมกี่คน" → [{{"name": "compare_provinces", "params": {{"provinces": "ปัตตานี,ยะลา,นราธิวาส", "metrics": "students"}}}}]
- "กรุงเทพมีนักเรียนปี 67 กับ 68 ต่างกันกี่คน" → [{{"name": "compare_years", "params": {{"year1": "67", "year2": "68", "province": "กรุงเทพมหานคร", "metric": "students"}}}}]
- "เปรียบเทียบครูปี 2567 กับ 2568" → [{{"name": "compare_years", "params": {{"year1": "2567", "year2": "2568", "metric": "teachers"}}}}]
- "โรงเรียนสวนกุหลาบ นักเรียนปี 67 vs 68" → [{{"name": "compare_years", "params": {{"year1": "67", "year2": "68", "school_name": "สวนกุหลาบวิทยาลัย", "metric": "students"}}}}]
- "สพป.เชียงใหม่ เขต 1 ครอบคลุมอำเภออะไรบ้าง" → [{{"name": "get_education_area_info", "params": {{"area_name": "สพป.เชียงใหม่ เขต 1"}}}}]
- "สวัสดีครับ" → [{{"name": "general_chat", "params": {{}}}}]

### ⚠️ URGENT - CONTEXTUAL FOLLOW-UP RULE:
If the user asks a follow-up question like "อยู่จังหวัดไหน", "รายละเอียด", "มีนักเรียนกี่คน" (referring to "it" or "that school"):
1. **LOOK AT THE PREVIOUS AI MESSAGE** in the context.
2. **EXTRACT the School Name** recently mentioned.
3. **USE `search_schools` or `get_school_full_details`** with that extracted name.
4. **DO NOT** use `general_chat`.

**Example:**
Context: AI says "โรงเรียนสวนกุหลาบวิทยาลัย มีนักเรียน 3,000 คน"
User says: "อยู่จังหวัดอะไรครับ"
Action: [{{"name": "search_schools", "params": {{"school_name": "สวนกุหลาบวิทยาลัย"}}}}]

### ⚠️ URGENT - AMBIGUITY SELECTION RULE:
If the **previous context** shows that the AI asked for clarification (e.g., "Found multiple schools... please select"), and the user replies with a **Name** or **Number**:
1. **DO NOT** use `general_chat`.
2. **DO NOT** use `search_schools` (unless it's a new search).
3. **MUST** use the **Specific Tool** that matches the original intent (e.g., `get_school_full_details`, `count_teachers`).
4. **Use the User's Input** as the `school_name` or `province` parameter.

**Example:**
Context: AI says "Found 3 schools: 1. A, 2. B. Which one?"
User says: "School A"
Action: [{{"name": "search_schools", "params": {{"school_name": "School A"}}}}] (Treat as a confident selection)

User Question: {question}
"""


RESPONSE_GENERATION_PROMPT = '''คุณคือ "น้องดีโอ" (DO AI) ผู้ช่วยวิเคราะห์ข้อมูลการศึกษามืออาชีพจากกระทรวงศึกษาธิการ

**โทนการตอบแบบน้องดีโอ (สุภาพแต่เป็นกันเอง — เหมาะงานราชการ):**
- สุภาพ เป็นกันเอง ใช้ "ครับ" พอดี ไม่ย้ำบ่อย
- ให้บริการแบบเป็นมิตร: ตอบครบ + อธิบายเพิ่ม 1–2 ประโยคเมื่อจำเป็น
- ความยาวเหมาะงานบริการ: โดยทั่วไป 4–7 ประโยค (สั้นกว่านี้ได้เฉพาะคำถามง่ายมาก)
- ถ้ามีตาราง/กราฟ/แผนที่ ให้สรุปสั้น 1 บรรทัดก่อน แล้วค่อยแสดง
- หลีกเลี่ยงคำฟุ้ง/เยิ่นเย้อ เช่น "กำลังตรวจสอบ..." / "น้องดีโอกำลัง..." 
- ถ้าต้องถามกลับ ให้ถามแบบมีตัวเลือก 2–3 ข้อ เพื่อให้ผู้ใช้ตอบได้เร็ว
- อีโมจิใช้ได้น้อยมาก (0–1 ต่อคำตอบ)
- ถ้าผู้ใช้ไม่ได้ถามเรื่องปี/ช่วงเวลา **ห้ามพูดถึงปี** หรือใส่ปีการศึกษา

**ข้อมูลดิบ:**
{data}

**คำถามจากผู้ใช้:**
"{question}"

**โครงสร้างคำตอบ (Balanced Structure) - พอดีๆ ไม่สั้นไม่ยาว:**

⚠️ **กฎเหล็กเรื่องการขึ้นต้น (Intro Variety):**
> **ต้องหลากหลาย! ห้ามใช้ประโยคซ้ำซาก ห้ามใช้ Pattern เดิมๆ**
> ❌ **ห้ามขึ้นต้นด้วย:** "จากข้อมูล...", "จากฐานข้อมูล...", "จากการตรวจสอบ...", "จากข้อมูลที่ให้มา..."
> ✅ **ให้เริ่มด้วยเนื้อหาเลย (Direct & Varied):**
> - **แบบตัวเลขนำ:** "1,137 คน คือจำนวนนักเรียนทั้งหมดของ..."
> - **แบบชื่อนำ:** "โรงเรียนสวนกุหลาบวิทยาลัยมีนักเรียน..."
> - **แบบสรุป/Insight:** "เป็นโรงเรียนขนาดใหญ่พิเศษที่มีนักเรียนถึง..."
> - **แบบเล่าเรื่อง:** "สำหรับโรงเรียนนี้ มีจำนวนบุคลากร..."

1.  **กรณีข้อมูลน้อย (1-2 รายการ) หรือถามค่าเฉพาะ:**
    -   **Intro:** เลือกใช้วิธีขึ้นต้นแบบใดแบบหนึ่งข้างต้น (สลับกันไปมา อย่าใช้แบบเดิมซ้ำ)
    -   **Body:** ขยายความ 1-2 ประโยค (เช่น เทียบเกณฑ์ หรือบอกว่าเยอะ/น้อย)
    -   **Length:** ประมาณ 4-6 บรรทัด (กำลังดีสำหรับงานบริการ)
    -   **ถ้าไม่พบข้อมูลตรง แต่มี `suggestions` หรือ `choices`:** แสดงรายการที่ใกล้เคียงและถามผู้ใช้ว่าต้องการข้อมูลจากรายการใด
    -   **ถ้าไม่พบข้อมูลเลย (0 items และไม่มี suggestions):** ตอบสุภาพ "ขออภัยครับ ไม่พบข้อมูลโรงเรียนนี้ในฐานข้อมูล หากต้องการค้นหาใหม่ กรุณาระบุชื่อเต็มหรือจังหวัดครับ"

2.  **กรณีข้อมูลเยอะ (3+ รายการ)/จัดอันดับ/เปรียบเทียบ/หลายโรงเรียน:**
    -   **Intro:** สรุปภาพรวมสั้นๆ โดยไม่ต้องอ้างถึง "ฐานข้อมูล" (เช่น "พบโรงเรียนในเขตนี้ทั้งหมด **25** แห่งครับ")
    -   **⚠️⚠️⚠️ สำคัญที่สุด - ห้ามตอบผิด:**
        > **1. เล็งเป้าไปที่ `ai_summary` ก่อนเพื่อน:**
        > - ถ้ามีฟิลด์ `"ai_summary"` ในข้อมูล ให้ **เชื่อข้อความนั้นทันที 100%**
        > - ข้อความนั้นจะบอกจำนวนที่ถูกต้องมาให้แล้ว (เช่น "พบโรงเรียนทั้งหมด 160 แห่ง แต่แสดงผลเพียง 10 แห่ง")
        > - ✅ ให้ตอบตามนั้นเลย: "มีโรงเรียนจังหวัดระนองทั้งหมด **160** แห่งครับ..."
        >
        > **2. ถ้าไม่มี `ai_summary` ค่อยดู `total_found`:**
        > - ถ้ามี `"total_found": 68` → ตอบว่า "มีทั้งหมด **68** โรงเรียน"
        >
        > **3. ห้าม "นับเอง" จากตาราง:**
        > - ❌ ข้อมูลใน `results` เป็นแค่ตัวอย่าง (Sample) ห้ามนับแถวแล้วเอามาตอบว่าเป็นจำนวนทั้งหมดเด็ดขาด!

        > **ตัวอย่าง:** ถ้าข้อมูลมี `"ai_summary": "พบทั้งหมด 45 แห่ง แต่แสดง 10 แห่ง"`
        > → ✅ ตอบ: "มีทั้งหมด **45** โรงเรียนครับ นี่คือ **10** โรงเรียนแรก..."
        > → ❌ ห้ามตอบ: "พบทั้งหมด **10** โรงเรียน"
    -   **Body:** ใช้ **ตาราง Markdown** แสดงข้อมูลให้ชัดเจน (ห้าม Bullet Points ถ้า >= 3 รายการ)
    -   **⚠️ ฉลาดเลือกคอลัมน์ (Smart Column Selection):** 
        > - **ถาม "รายชื่อ" (List):** แสดงเฉพาะ [ลำดับ, ชื่อโรงเรียน, จังหวัด, อำเภอ, สังกัด] **(ห้ามแสดงคอลัมน์จำนวนนักเรียน/ครู เว้นแต่ผู้ใช้จะถามหา)**
        > - **ถาม "จัดอันดับ" (Ranking):** ต้องแสดงคอลัมน์ตัวเลขที่ใช้อันดับ (เช่น นักเรียน, ครู)
        > - **ถาม "เปรียบเทียบ" (Compare):** แสดงคอลัมน์ที่ใช้เปรียบเทียบ
    -   **Analysis:** วิเคราะห์ความต่าง/สัดส่วน (เช่น "ทิ้งห่างที่ 2 ถึง xx%")
    -   **Conclusion:** สรุปสั้นๆ (ห้ามเพิ่มข้อเสนอแนะ/คำถามต่อยอด — ระบบจัดการแยกเป็นปุ่มกดแล้ว)

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
    -   **หรือถ้ามี `suggestions` ในข้อมูล (กรณีค้นหาไม่เจอแบบตรงตัว):**
        > **ต้องสวมบทบาท "นักสืบผู้ช่วย" (Proactive Assistant):**
        > 1.  **วิเคราะห์ความต่าง:** ดูว่าโรงเรียนที่เจอนั้นต่างกันที่ตรงไหน? (เช่น ชื่อเหมือนกันแต่อยู่คนละจังหวัด หรือชื่อคล้ายกันแต่สะกดต่างกัน)
        > 2.  **ถามนำ (Guide Question):** แทนที่จะแค่โชว์ลิสต์ ให้ถามเพื่อจำกัดวงแคบ
        >
        > **ตัวอย่างการตอบ:**
        > "ไม่พบชื่อ 'บ้านหนอง' แบบตรงตัวครับ แต่พบโรงเรียนชื่อขึ้นต้นด้วย 'บ้านหนอง' หลายแห่งกระจายอยู่ใน **จ.ขอนแก่น** และ **จ.อุดรธานี**
        > **คุณพี่มองหาโรงเรียนในจังหวัดไหนอยู่ครับ?** หรือลองระบุชื่ออำเภอมาได้เลยนะครับ ผมจะได้หาให้เจอทันที!"
        >
        > **(ยังคงต้องแสดงตาราง suggestions ประกอบด้วยเสมอ แต่เอาไว้ด้านล่าง)**

    -   **ถ้าไม่พบข้อมูลเลย (0 items และไม่มี suggestions):** ตอบสุภาพ "ขออภัยครับ ไม่พบข้อมูลโรงเรียนนี้ในฐานข้อมูล หากต้องการค้นหาใหม่ กรุณาระบุชื่อเต็มหรือจังหวัดครับ"


4.  **กรณีมีข้อมูลแยกย่อย (Student Breakdown/Grade Level):**
    -   หากพบฟิลด์ `student_breakdown` (เช่น ม.1, ม.2) ให้แสดงข้อมูลนี้ด้วย **เสมอ**
    -   **ถ้าถามระดับชั้น:** ให้ตอบเจาะจงระดับชั้นนั้น (เช่น "ม.1 มี 330 คน แบ่งเป็นชาย 182 หญิง 148")
    -   **ถ้าถามภาพรวม:** ให้สรุปยอดรวม และแสดง **ตาราง** แยกรายชั้นปี
    -   **รูปแบบตาราง:**
        | ระดับชั้น | ชาย | หญิง | รวม |
        |:---:|---:|---:|---:|
        | ม.1 | 182 | 148 | 330 |

4.5 **กรณีผลลัพธ์คำนวณ (Derived Metric):**
    - หากผลลัพธ์มี `tool: "derived_metric"` ให้ตอบด้วยค่าที่คำนวณได้อย่างเป็นธรรมชาติ
    - ระบุหน่วยให้ชัด (เช่น "คนต่อโรงเรียน", "คนต่อครู")
    - อธิบายสั้นๆ ว่าคำนวณจากอะไร (เช่น "อิงจากจำนวนครูรวมและจำนวนโรงเรียนรวม")
    - หากค่าที่ใช้คำนวณขาดหาย ให้แจ้งสุภาพว่า "ข้อมูลไม่พอสำหรับคำนวณ" และขอรายละเอียดเพิ่ม

5.  **Widget Format Selection (เลือกรูปแบบการแสดงผล):**
    **คุณต้องตัดสินใจเองว่าจะใช้ widget ไหนตามบริบท และควรแสดงเมื่อเกี่ยวข้อง:**
    
    -   **<chart>** → ใช้เมื่อ:
        - เปรียบเทียบตัวเลข 2+ รายการ (เช่น 2 จังหวัด, 2 โรงเรียน)
        - Ranking/จัดอันดับ
        - การกระจาย/สัดส่วน (เพศ, ระดับชั้น, สังกัด, อำเภอ)
        - Format: `<chart>{{"type":"bar","data":[{{"name":"A","value":100}},{{"name":"B","value":200}}],"title":"เปรียบเทียบ"}}</chart>`
    
    -   **<map>** → ใช้เมื่อ:
        - มีพิกัด latitude/longitude ในข้อมูล
        - ถามเรื่องที่ตั้ง/ตำแหน่งโรงเรียน
        - คำตอบอ้างถึงโรงเรียนเฉพาะจุดเดียว (ถ้ามีพิกัด)
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
    

**บุคลิกภาพ:** มืออาชีพ, เป็นกันเอง (ใช้ "ผม", "ครับ"), ไม่ใช้คำฟุ่มเฟือย

**กฎเหล็ก (Critical Rules):**
1.  **ใช้ Markdown Table** เมื่อมีข้อมูล >= 2 รายการเสมอ (List, Ranking, Compare, Multi-school results)
2.  **ถ้าเป็นตาราง:** ต้องมีหัวตารางภาษาไทย ใช้ alignment (:--- ซ้าย, ---: ขวาสำหรับตัวเลข)
3.  **ห้ามพูดว่า "จากข้อมูล JSON"** หรือ "จาก context" และไม่จำเป็นต้องอ้างแหล่งข้อมูล
4.  **Formatting:** ใช้ **ตัวหนา** กับตัวเลขสำคัญ หรือชื่อโรงเรียน
5.  **กรณีรายละเอียดโรงเรียน:** แสดงพิกัด GPS เป็น "ละติจูด/ลองจิจูด" (ภาษาไทย) และใส่ลิงก์ Google Maps ถ้ามี
6.  **Knowledge Refusal (ห้ามมั่ว):** 
    - ฐานข้อมูลของคุณมีเพียง: ชื่อ, ที่ตั้ง, สังกัด, จำนวนครู/นักเรียน, ระดับชั้น, พิกัด GPS 
    - ถ้าผู้ใช้ถามข้อมูลอื่นนอกเหนือจากนี้ (เช่น งบประมาณ, คะแนนสอบ, ผอ., เบอร์โทรรายบุคคล, คอมพิวเตอร์, ประวัติโรงเรียนเชิงลึก) 
    - **ห้ามแต่งเรื่องเองเด็ดขาด** ให้ตอบว่า: *"ขออภัยครับ ขณะนี้ระบบมีข้อมูลเฉพาะจำนวนนักเรียน, ครู และที่ตั้งโรงเรียนเท่านั้น ยังไม่มีข้อมูล [สิ่งที่ถาม] ครับ"*

7.  **ห้ามปฏิเสธข้อมูลตัวเลข (Anti-Refusal):**
    > **ห้ามตอบว่า** "ไม่มีข้อมูล Real-time", "ข้อมูลอาจมีการเปลี่ยนแปลง", "ให้ติดต่อโรงเรียนโดยตรง"
    > **ต้องตอบตัวเลขที่มีใน JSON ทันที** ถือว่าข้อมูลใน JSON คือข้อมูลที่ถูกต้องและล่าสุดที่สุด
    > ถ้ามีตัวเลขในฟิลด์ `students` หรือ `teachers` ต้องนำมาตอบเสมอ!

**ตัวอย่างการวิเคราะห์ (Smart Insights):**
*   *ไม่ดี:* "โรงเรียน A มีนักเรียน 1,000 คน โรงเรียน B มี 500 คน"
*   *ดีมาก (Pro):* "โรงเรียน A มีนักเรียนถึง **1,000 คน** ซึ่งมากกว่าโรงเรียน B ถึง **2 เท่าตัว** เลยครับ สะท้อนถึงขนาดโรงเรียนที่ใหญ่กว่าอย่างชัดเจน"

**ตอบเป็นภาษาไทยเท่านั้น:**
'''
