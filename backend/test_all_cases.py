import os
import sys
import logging
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

logging.basicConfig(level=logging.WARNING, format='%(name)s - %(levelname)s - %(message)s')

from chatbot.llm_agent import LLMAgent
from chatbot.llm import MultiProviderLLM
from chatbot.entity_extractor import _get_qdrant_client

def run_tests():
    print("🚀 Initializing Comprehensive Test Suite...")
    qdrant = _get_qdrant_client()
    llm = MultiProviderLLM()
    agent = LLMAgent(qdrant, llm)
    
    test_cases = [
        {
            "category": "1. ทดสอบ Reflection Loop (พิมพ์ผิด/เงื่อนไขลึกเกินไป)",
            "query": "โรงเรียนในอำเภอบางบ่อ จังหวัดเชียงใหม่ มีกี่แห่ง",
            "expected": "ควร Reflect ไปหาข้อมูลของ 'จังหวัดเชียงใหม่' มารายงานแทน"
        },
        {
            "category": "2. ทดสอบ Ranking & Scope (ซับซ้อนขึ้น)",
            "query": "อำเภอไหนในภาคใต้ที่มีโรงเรียนเยอะที่สุด",
            "expected": "ควรใช้ tool: ranking(metric=schools, order=most, scope=district, region=ภาคใต้)"
        },
        {
            "category": "3. ทดสอบการดึงข้อมูลเฉพาะเจาะจงสูง",
            "query": "โรงเรียนเบตง มียอดนักเรียนชั้น ม.6 กี่คน และมีครูอัตราจ้างไหม",
            "expected": "ควรดึงข้อมูล get_school_full_details หรือใช้ 2 tools พร้อมกัน"
        },
        {
            "category": "4. ทดสอบคำถามแบบกำกวม/กว้างเกินไป (Ask-back)",
            "query": "อยากรู้ว่าโรงเรียนไหนดีสุด",
            "expected": "ควรตอบว่า 'ดีสุดในแง่ไหนครับ? อัตราส่วนครูต่อนักเรียนหรือจำนวนนักเรียน?' (Ask-back)"
        },
        {
            "category": "5. ทดสอบคำถามเชิงเปรียบเทียบ (Multi-step หรือ Tool เฉพาะ)",
            "query": "เด็กนักเรียนในเชียงใหม่กับเชียงราย จังหวัดไหนเยอะกว่ากัน",
            "expected": "ควรใช้ tool compare_provinces หรือ compare"
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n========================================================")
        print(f"📌 Case {i}: {test['category']}")
        print(f"👤 User: {test['query']}")
        print(f"🎯 Expected Behavior: {test['expected']}")
        print(f"--------------------------------------------------------")
        
        try:
            response, active_query = agent.process_query(test['query'])
            print(f"🤖 Bot (Natural Response): \n{response}\n")
            print(f"🔧 Tool Executed: {active_query}")
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    run_tests()
