import os
import sys
import logging
from dotenv import load_dotenv
import json

# Setup path and logging
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
logging.basicConfig(level=logging.INFO)
load_dotenv(os.path.join(os.path.dirname(__file__), '../.env'))

from backend.chatbot.tool_executor import ToolExecutor
from backend.chatbot.llm import MultiProviderLLM
from qdrant_client import QdrantClient

def test_south_region_search():
    print("🚀 Initializing Components...")
    client = QdrantClient(host="localhost", port=6333)
    llm = MultiProviderLLM()
    executor = ToolExecutor(qdrant_client=client, llm_provider=llm)

    print("\n🔍 Test 1: Search 'Most students in South' (Expect Southern schools)")
    # This maps to what the LLM likely calls for "ขอข้อมูลโรงเรียนในภาคใต้ว่าจังหวัดไหนมีนักเรียนมากกที่สุด"
    # Likely `ranking` or `search_schools` or `filter_schools`?
    # Given the user query asked for "which province has most students", it might be a ranking.
    # But let's check basic filtering first.
    
    # Simulate tool call for "Schools in South region with most students"
    # Potentially `ranking` tool
    params = {
        "metric": "students",
        "order": "most",
        "scope": "region",
        "region": "ภาคใต้",
        "limit": 5
    }
    
    print(f"🔧 Executing 'ranking' with params: {params}")
    try:
        result = executor.execute("ranking", params)
        print(f"📊 Result:\n{result}")
        
        # Check ranking result
        ranking = result.get('ranking', [])
        found_invalid = False
        
        for item in ranking:
            name = item.get('name', 'Unknown')
            # Check if this school is in Chonburi (E-Tech is in Chonburi)
            if "ภาคตะวันออก" in name or "อี.เทค" in name or "ชลบุรี" in name: # Metadata usually not here, just name
                 # Fetch full details to check province? Or just rely on known bad output
                 if "อี.เทค" in name:
                     found_invalid = True
                     print(f"❌ Found E-Tech: {name}")

        if found_invalid:
             print("\n❌ FAIL: Found 'E-Tech' (Chonburi) in South results! Filter is BROKEN.")
        else:
             print("\n✅ PASS: No E-Tech found in South results.")
             # Print top 3 for verification
             for r in ranking[:3]:
                 print(f"   #{r['rank']} {r['name']} ({r['count']})")
             
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_south_region_search()
