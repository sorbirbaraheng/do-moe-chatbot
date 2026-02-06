import os
import sys
import logging
from dotenv import load_dotenv

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
logging.basicConfig(level=logging.INFO)
load_dotenv(os.path.join(os.path.dirname(__file__), '../.env'))

from backend.chatbot.tool_executor import ToolExecutor
from backend.chatbot.llm import MultiProviderLLM
from qdrant_client import QdrantClient

def verify_suankularb():
    print("🚀 Initializing Components...")
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    print(f"📡 Connecting to Qdrant at: {qdrant_url}")
    client = QdrantClient(url=qdrant_url)
    llm = MultiProviderLLM()
    executor = ToolExecutor(qdrant_client=client, llm_provider=llm)
    
    print("\n🔍 Test: Search for 'สวนกุหลาบ' (Expect multiple branches)")
    # User's query concept: "Where are Suankularb schools?" -> implies searching by name
    params = {
        "school_name": "สวนกุหลาบ",
        "limit": 10
    }
    
    print(f"🔧 Executing 'search_schools' with params: {params}")
    try:
        result = executor.execute("search_schools", params)
        
        schools = result.get('results', [])
        summary = result.get('ai_summary', '')
        
        print(f"📝 Summary: {summary}")
        print(f"🔢 Found: {len(schools)} schools")
        
        for s in schools:
            print(f"   - {s.get('school_name')} ({s.get('province')})")
            
        # Check if we got major branches
        names = [s.get('school_name', '') for s in schools]
        has_main = any("สวนกุหลาบวิทยาลัย" in n for n in names)
        has_non = any("นนทบุรี" in n for n in names)
        
        if has_main:
            print("✅ Found main Suankularb")
        else:
            print("⚠️ Main Suankularb NOT found")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    verify_suankularb()
