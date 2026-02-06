import os
import sys
import logging
from dotenv import load_dotenv
from qdrant_client import QdrantClient

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
env_path = os.path.join(os.path.dirname(__file__), '../.env')
load_dotenv(env_path)

from backend.chatbot.tool_executor import ToolExecutor
from backend.chatbot.llm import MultiProviderLLM

def verify_all_suankularb():
    print("🚀 Initializing Components...")
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    client = QdrantClient(url=qdrant_url)
    llm = MultiProviderLLM()
    executor = ToolExecutor(qdrant_client=client, llm_provider=llm)
    
    print("\n🔍 Test: Search for 'สวนกุหลาบ' with limit=50")
    # Bypass tool_executor's default limit to see raw results from engine if possible
    # But we want to test tool_executor logic too.
    
    # calling _smart_search_school directly to see raw output
    print("--- Calling _smart_search_school directly ---")
    results = executor._smart_search_school("สวนกุหลาบ", limit=50)
    
    print(f"🔢 Total Found via _smart_search_school: {len(results)}")
    
    print("\n📋 List of Schools Found:")
    found_main = False
    for i, res in enumerate(results, 1):
        meta = res.payload.get('metadata', {}) if hasattr(res, 'payload') else res
        name = meta.get('school_name', '')
        prov = meta.get('province', '')
        print(f"{i}. {name} ({prov})")
        
        if name.strip() == "โรงเรียนสวนกุหลาบวิทยาลัย" or name.strip() == "สวนกุหลาบวิทยาลัย":
            found_main = True
            print("   ✅ FOUND MAIN BRANCH!")

    if not found_main:
        print("\n❌ MAIN BRANCH 'โรงเรียนสวนกุหลาบวิทยาลัย' NOT FOUND!")

if __name__ == "__main__":
    verify_all_suankularb()
