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

def verify_all_regions():
    print("🚀 Initializing Components...")
    client = QdrantClient(host="localhost", port=6333)
    llm = MultiProviderLLM()
    executor = ToolExecutor(qdrant_client=client, llm_provider=llm)
    
    # 1. Test Teachers in North (Expect NO Bangkok/South schools)
    print("\n🔍 Test 1: Count Teachers in NORTH (ภาคเหนือ)")
    res1 = executor.execute("count_teachers", {"region": "ภาคเหนือ"})
    print(f"   - Total Teachers: {res1.get('total_teachers')}")
    print(f"   - Schools Found: {res1.get('total_found')}")
    # Verify top schools are in North
    top_schools = res1.get('by_school', {})
    print(f"   - Top 3 Schools: {list(top_schools.keys())[:3]}")
    # We can't easily auto-verify province of SCHOOL result without more calls, 
    # but we can check if count > 0 and assume filter works if numbers aren't huge national totals
    
    # 2. Test Schools in Central (Expect Bangkok schools)
    print("\n🔍 Test 2: Count Schools in CENTRAL (ภาคกลาง)")
    res2 = executor.execute("count_schools", {"region": "ภาคกลาง"})
    print(f"   - Total Schools: {res2.get('total_schools')}")
    # Verify provinces in summary?
    
    # 3. Test Students in South (Retest Fix)
    print("\n🔍 Test 3: Count Students in SOUTH (ภาคใต้)")
    res3 = executor.execute("ranking", {"metric": "students", "region": "ภาคใต้", "limit": 3})
    ranking = res3.get('ranking', [])
    for r in ranking:
        print(f"   - #{r['rank']} {r['name']} ({r['count']})")
        
    if any("อี.เทค" in r['name'] for r in ranking):
        print("❌ FAIL: E-Tech still in South!")
    else:
        print("✅ PASS: South is clean.")

if __name__ == "__main__":
    verify_all_regions()
