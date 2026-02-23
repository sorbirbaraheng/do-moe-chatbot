import os
import sys
import logging
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from chatbot.llm_agent import LLMAgent
from chatbot.llm import MultiProviderLLM
from chatbot.entity_extractor import _get_qdrant_client
import json

def test_teacher_query():
    print("🚀 Initializing Specific Test...")
    qdrant = _get_qdrant_client()
    
    # Force Gemini by hiding Groq keys
    keys_to_del = [k for k in os.environ if k.startswith("GROQ_API_KEY")]
    for k in keys_to_del:
        del os.environ[k]
        
    llm = MultiProviderLLM()
    agent = LLMAgent(qdrant, llm)
    
    test_query = "จังหวัดไหนมีครูอัตราจ้างน้อยที่สุด"
    
    print(f"\n❓ Question: {test_query}\n")
    # By passing `None` as context, we can isolate just the extraction part
    tool_calls = agent._select_tools(test_query, None)
    print("\n🔍 Extracted Tools:")
    print(json.dumps(tool_calls, ensure_ascii=False, indent=2))
    
    print("\n🔧 Executing Tools:")
    for t in tool_calls:
        res = agent.tool_executor.execute(t["name"], t.get("params", {}))
        print("Data sample:")
        print(str(res)[:500] + "...")

if __name__ == "__main__":
    test_teacher_query()
