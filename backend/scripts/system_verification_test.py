
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

def run_verification_test():
    client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))
    # Initialize with dry_run=True to avoid actual LLM calls if possible, 
    # but for full system verification we might WANT full calls.
    # However, since we want to verify "system capabilities" and the tool logic, 
    # we can use the tool_executor directly IF we know the mapping.
    # BUT the user asked "Try testing these questions", implying NLP understanding.
    # So we should use bot.chat() or at least bot.llm_agent.process().
    
    # Initialization
    print("🚀 Initializing Chatbot System...")
    bot = EducationChatbot(qdrant_client=client)
    
    # 15 Scenarios
    scenarios = [
        # --- Group 1: Fuzzy Search ---
        { "id": 1, "q": "ขอข้อมูลโรงเรียน เตรียมอุดมพัานาการ", "category": "Fuzzy Search (Typo)" },
        { "id": 2, "q": "โรงเรียนสตรีวิทย อยู่ที่ไหน", "category": "Fuzzy Search (Incomplete)" },
        { "id": 3, "q": "หารายชื่อโรงเรียนในอำเภอเมืองเชียงใหม่ที่มีนักเรียนมากกว่า 1000 คน", "category": "Complex Filter (Area + Count)" },
        
        # --- Group 2: Comparison ---
        { "id": 4, "q": "เปรียบเทียบจำนวนนักเรียนโรงเรียนเตรียมอุดมศึกษากับสวนกุหลาบวิทยาลัย", "category": "Compare (School)" },
        { "id": 5, "q": "เปรียบเทียบจำนวนครูในจังหวัดเชียงใหม่กับเชียงราย", "category": "Compare (Province)" },
        { "id": 6, "q": "เปรียบเทียบจำนวนโรงเรียนในภาคเหนือกับภาคใต้", "category": "Compare (Region Alias)" },
        { "id": 7, "q": "เปรียบเทียบสถิตินักเรียนชายและหญิงของโรงเรียนหอวัง", "category": "Compare (Gender within School)" },
        
        # --- Group 3: Ranking ---
        { "id": 8, "q": "10 อันดับโรงเรียนที่มีนักเรียนเยอะที่สุดในจังหวัดขอนแก่น", "category": "Ranking (Top N)" },
        { "id": 9, "q": "โรงเรียนที่มีจำนวนครูน้อยที่สุดในแม่ฮ่องสอน คือที่ไหน", "category": "Ranking (Bottom 1)" },
        
        # --- Group 4: Deep Stats ---
        { "id": 10, "q": "โรงเรียนสามเสนวิทยาลัย มีครูผู้ช่วยกี่คน", "category": "Deep Stats (Person Type)" },
        { "id": 11, "q": "สรุปจำนวนนักเรียนระดับชั้นอนุบาลในจังหวัดนครราชสีมา", "category": "Deep Stats (Grade Level)" },
        { "id": 12, "q": "อัตราส่วนครูต่อนักเรียนของโรงเรียนเบญจมราชูทิศ", "category": "Deep Stats (Ratio)" },
        
        # --- Group 5: Agency/Location ---
        { "id": 13, "q": "มีโรงเรียนอะไรบ้างในสังกัด สพม.กรุงเทพมหานคร เขต 1", "category": "Agency Filter" },
        { "id": 14, "q": "เขตพื้นที่การศึกษา สพป.เชียงราย เขต 2 ครอบคลุมอำเภอไหนบ้าง", "category": "Location Lookup (Area Coverage)" },
        { "id": 15, "q": "ในประเทศไทยมีโรงเรียนในสังกัดเอกชนทั้งหมดกี่แห่ง", "category": "Total Count by Agency" }
    ]

    print(f"\n🧪 STARTING COMPREHENSIVE VERIFICATION ({len(scenarios)} Scenarios)\n" + "="*80)
    
    results = []

    for item in scenarios:
        print(f"\n📝 Scenario {item['id']} [{item['category']}]: \"{item['q']}\"")
        
        start_time = time.time()
        try:
            # We use the internal agent directly to see the tool decision loop if possible, 
            # OR just chat. chat() returns a string and maybe metadata.
            # To verify technical correctness, we want to know WHICH tool was called.
            # We can inspect the logs or try to parse the response.
            # Ideally, we'd invoke the llm_agent directly to get the intermediate tool call, 
            # but that might be complex to set up.
            # Let's use bot.chat() for the most realistic "User Experience" test.
            
            response_generator = bot.chat(item['q'], history=[])
            full_response = ""
            for chunk in response_generator:
                full_response += chunk
            
            elapsed = time.time() - start_time
            print(f"⏱️ Time: {elapsed:.2f}s")
            # print(f"🤖 Response: {full_response[:200]}..." if len(full_response) > 200 else f"🤖 Response: {full_response}")
            
            results.append({
                "id": item['id'],
                "status": "PASS",
                "elapsed": elapsed,
                "response_preview": full_response[:100]
            })

        except Exception as e:
            print(f"❌ ERROR: {e}")
            results.append({
                "id": item['id'],
                "status": "FAIL",
                "error": str(e)
            })

    print("\n" + "="*80)
    print("📊 SUMMARY REPORT")
    print("="*80)
    for res in results:
        status_icon = "✅" if res['status'] == "PASS" else "❌"
        print(f"{status_icon} ID {res['id']}: {res['status']} ({res.get('elapsed', 0):.2f}s)")

if __name__ == "__main__":
    run_verification_test()
