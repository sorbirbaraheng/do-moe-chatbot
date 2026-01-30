
import sys
import os
import json
import logging
import time

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from chatbot.chatbot_core import EducationChatbot
from qdrant_client import QdrantClient

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_deep_test():
    client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))
    bot = EducationChatbot(qdrant_client=client)
    executor = bot.llm_agent.tool_executor
    
    questions = [
        # 1. Complex Filter: District + Count
        {
            "id": 1,
            "q": "ขอรายชื่อโรงเรียนในอำเภอเมืองเชียงใหม่ที่มีนักเรียนมากกว่า 2000 คน",
            "tool": "list_schools",
            "params": {"district": "อำเภอเมืองเชียงใหม่", "province": "เชียงใหม่", "min_students": 2000}
        },
        # 2. Fuzzy Compare: Typo in School Name
        {
            "id": 2,
            "q": "เปรียบเทียบนักเรียนระหว่าง โรงเรียนสตรีวิทย กับ สวนกุหลาบวิทยาลัย", 
            "tool": "compare",
            # Assuming LLM extracted these entities. "สตรีวิทย" is a prefix typo
            "params": {"entity1": "สตรีวิทย", "entity2": "สวนกุหลาบวิทยาลัย", "metric": "students"}
        },
        # 3. Cross-Province Compare
        {
            "id": 3,
            "q": "เปรียบเทียบจำนวนครูระหว่าง จังหวัดเชียงราย กับ พะเยา",
            "tool": "compare",
            "params": {"entity1": "เชียงราย", "entity2": "พะเยา", "metric": "teachers"}
        },
        # 4. Specific Personnel Type
        {
            "id": 4,
            "q": "โรงเรียนยุพราชวิทยาลัย มีครูผู้ช่วยกี่คน",
            "tool": "count_teachers",
            "params": {"school_name": "ยุพราชวิทยาลัย", "person_type": "ครูผู้ช่วย"}
        },
        # 5. Ratio Lookup
        {
            "id": 5,
            "q": "อัตราส่วนครูต่อนักเรียนของโรงเรียนเตรียมอุดมศึกษา",
            "tool": "get_ratio",
            "params": {"school_name": "เตรียมอุดมศึกษา", "province": "กรุงเทพมหานคร"}
        },
        # 6. Ranking
        {
            "id": 6,
            "q": "5 อันดับโรงเรียนที่มีนักเรียนเยอะที่สุดในขอนแก่น",
            "tool": "ranking",
            "params": {"province": "ขอนแก่น", "metric": "students", "order": "most", "limit": 5}
        },
        # 7. Pure Fuzzy Search (Expect Suggestions)
        {
            "id": 7,
            "q": "ขอข้อมูลโรงเรียน เตรียมอุดมพัานาการ",
            "tool": "get_school_full_details",
            "params": {"school_name": "เตรียมอุดมพัานาการ"}
        },
        # 8. Education Area List (Agency)
        {
            "id": 8,
            "q": "โรงเรียนในสังกัด สพม.กรุงเทพมหานคร เขต 1",
            "tool": "list_schools",
            "params": {"agency": "สพม.กรุงเทพมหานคร เขต 1", "limit": 5}
        },
        # 9. Gender Breakdown
        {
            "id": 9,
            "q": "โรงเรียนวัฒนาวิทยาลัย มีนักเรียนชายกี่คน",
            "tool": "count_students",
            "params": {"school_name": "วัฒนาวิทยาลัย"}
        },
        # 10. Edge Case: Non-existent
        {
            "id": 10,
            "q": "ข้อมูลโรงเรียนฮอกวอตส์",
            "tool": "get_school_full_details",
            "params": {"school_name": "ฮอกวอตส์"} 
        }
    ]

    print(f"\n🚀 STARTING DEEP DIVE TEST ({len(questions)} Scenarios)\n" + "="*60)
    
    for item in questions:
        print(f"\n📝 Scenario {item['id']}: {item['q']}")
        print(f"🔧 Tool: {item['tool']} | Params: {item['params']}")
        
        try:
            start_time = time.time()
            result = executor.execute(item['tool'], item['params'])
            elapsed = time.time() - start_time
            
            # Simple validation prints
            status = "✅ OK"
            note = ""
            
            if item['tool'] == 'compare':
                if not result.get('entity1', {}).get('data') and not result.get('entity1', {}).get('suggestions'):
                     status = "⚠️ Partial/Empty"
            
            if item['id'] == 7: # Expect suggestions
                if not result.get('suggestions'):
                    status = "❌ FAIL (Expected Suggestions)"
                else:
                    note = f"(Got {len(result['suggestions'])} suggestions)"

            if item['id'] == 10: # Expect not found
                if result.get('found', True):
                     status = "⚠️ Unexpected Found"
                else:
                    status = "✅ OK (Not Found as expected)"

            print(f"📊 Result: {status} {note} in {elapsed:.4f}s")
            
            # Print condensed JSON for review
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
        except Exception as e:
            print(f"❌ CRITICAL ERROR: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*60 + "\n🏁 TEST COMPLETE")

if __name__ == "__main__":
    run_deep_test()
