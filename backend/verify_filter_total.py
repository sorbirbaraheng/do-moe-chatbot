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

def verify_filter_count():
    print("🚀 Initializing Components...")
    client = QdrantClient(host="localhost", port=6333)
    llm = MultiProviderLLM()
    executor = ToolExecutor(qdrant_client=client, llm_provider=llm)
    
    print("\n🔍 Test 1: Filter Schools > 500 Students in Chonburi")
    # User's query: "schools with > 500 students in Chonburi"
    params = {
        "metric": "students",
        "operator": "gt",
        "value": 500,
        "province": "ชลบุรี",
        "limit": 10
    }
    
    print(f"🔧 Executing 'filter_schools' with params: {params}")
    try:
        result = executor.execute("filter_schools", params)
        
        # 'filter_schools' returns a list of dictionaries directly in 'schools' or 'results'? 
        # Check tool_executor.py: _filter_schools returns a dict with 'schools', 'ai_summary', etc?
        # WAIT: The return value of _filter_schools in tool_executor.py (lines 1956+) is NOT a dict wrapper?
        # Let's check the return statement in tool_executor.py first.
        
        print(f"📊 Result keys: {result.keys() if isinstance(result, dict) else 'Not a dict'}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    verify_filter_count()
