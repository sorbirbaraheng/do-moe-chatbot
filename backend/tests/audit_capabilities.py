
import os
import sys
import logging
from dotenv import load_dotenv

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chatbot.chatbot_core import EducationChatbot
from chatbot.llm_agent import LLMAgent

from qdrant_client import QdrantClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def run_audit():
    print("="*60)
    print("🤖 Chatbot Capability Audit")
    print("="*60)

    try:
        # Initialize Qdrant Client
        qdrant_host = os.getenv("QDRANT_HOST", "203.159.242.144")
        qdrant_port = int(os.getenv("QDRANT_PORT", 6333))
        print(f"🔌 Connecting to Qdrant at {qdrant_host}:{qdrant_port}...")
        client = QdrantClient(host=qdrant_host, port=qdrant_port)

        # Initialize Chatbot
        print("🔌 Initializing Chatbot...")
        bot = EducationChatbot(qdrant_client=client)
        
        # Test Queries covering all categories
        test_queries = [
            # 1. School Counts (Stats)
            "ปัตตานีมีโรงเรียนกี่แห่ง",
            "อำเภอเมืองยะลามีโรงเรียนสังกัด สพฐ. กี่แห่ง",
            
            # 2. Student/Teacher Counts (Stats)
            "จังหวัดนราธิวาสมีครูผู้หญิงกี่คน",
            "อำเภอเบตงมีนักเรียนชั้น ม.6 กี่คน",
            "มีนักเรียนทั้งหมดกี่คนในจังหวัดสตูล",
            
            # 3. Ranking
            "จังหวัดไหนในภาคใต้มีโรงเรียนมากที่สุด", 
             # Note: "ภาคใต้" might fail if not handled, relying on "จังหวัดไหน...มากที่สุด"
            "5 อันดับอำเภอในเชียงใหม่ที่มีนักเรียนน้อยที่สุด",
            "โรงเรียนไหนในกรุงเทพมีครูเยอะที่สุด",
            
            # 4. Comparison
            "เปรียบเทียบจำนวนโรงเรียนระหว่าง ยะลา กับ ปัตตานี",
            "เทียบจำนวนครูของโรงเรียนเตรียมอุดม กับ โรงเรียนสวนกุหลาบ",
            
            # 5. Search / Details
            "ขอข้อมูลโรงเรียนราชประชานุเคราะห์ 40",
            "โรงเรียนเบญจมราชูทิศ อยู่ที่ไหน",
            
            # 6. Ratios / Quality
            "อัตราส่วนครูต่อนักเรียนของโรงเรียนเตรียมอุดม",
            
            # 7. General Knowledge (should respond with LLM)
            "นโยบายการศึกษาปีนี้เป็นอย่างไร",
            
            # 8. Edge Cases / Complex
            "ค้นหาโรงเรียนที่มีคำว่า 'อนุบาล' ในเชียงใหม่",
            "อำเภอไหนมีโรงเรียนน้อยกว่า 10 แห่ง" # Hard filter
        ]
        
        results = []
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n🔹 Test {i}: {query}")
            try:
                # We want to see the Tool Selection and the Final Response
                # Accessing internal agent for inspection
                agent = bot.llm_agent
                
                print("   Processing...")
                
                # 1. Tool Selection (Simulated inspection)
                tool_calls = agent._select_tools(query)
                tool_names = [t['name'] for t in tool_calls] if tool_calls else ["NO TOOL (General/Fallback)"]
                
                print(f"   🛠️  Selected Tools: {tool_names}")
                if tool_calls:
                    print(f"      Params: {tool_calls[0].get('params')}")

                # 2. Full Execution
                # We use the public method to see the final string response
                response = agent.process_query(query)
                
                # Summary checks
                status = "✅ PASS"
                if "ไม่พบข้อมูล" in response or "ขออภัย" in response:
                    status = "⚠️ WARNING (Not Found / Error)"
                if "Error" in response or "Exception" in response:
                    status = "❌ FAIL (Exception)"
                
                print(f"   📝 Response Snippet: {response[:150]}...")
                print(f"   Status: {status}")
                
            except Exception as e:
                print(f"   ❌ CRITICAL FAIL: {e}")
                
            print("-" * 30)
            
    except Exception as e:
        print(f"\n❌ Fatal Error initializing chatbot: {e}")

if __name__ == "__main__":
    run_audit()
