
import os
import sys
import json
# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from chatbot.tool_executor import ToolExecutor

from qdrant_client import QdrantClient

def test_count_teachers():
    # Initialize real Qdrant Client
    qdrant = QdrantClient(url="http://203.159.242.144:6333")
    
    executor = ToolExecutor(qdrant_client=qdrant)
    
    print("🧪 Testing _count_teachers for Region: ภาคใต้")
    
    # 1. Test purely the tool execution
    result = executor.execute(
        "count_teachers",
        {"region": "ภาคใต้"}
    )
    
    print("\n📊 Tool Result:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # Check if we got a valid number
    total = result.get("total_teachers", 0)
    if total > 0:
        print(f"\n✅ PASS: Found {total} teachers in South.")
    else:
        print(f"\n❌ FAIL: Found 0 teachers. This explains why the LLM hallucinated.")

if __name__ == "__main__":
    test_count_teachers()
