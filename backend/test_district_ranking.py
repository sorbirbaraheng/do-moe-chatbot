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

def test_specific_query():
    print("🚀 Initializing Specific Test...")
    qdrant = _get_qdrant_client()
    
    # Force Groq by hiding Gemini key
    old_gemini = os.environ.get("GEMINI_API_KEY")
    if "GEMINI_API_KEY" in os.environ:
        del os.environ["GEMINI_API_KEY"]
        
    llm = MultiProviderLLM()
    agent = LLMAgent(qdrant, llm)
    
    print("\n🔧 Executing Tool Directly:")
    res = agent.tool_executor.execute("ranking", {
        "metric": "schools", 
        "scope": "district", 
        "region": "ภาคใต้", 
        "order": "most", 
        "limit": 3
    })
    
    print("\n✅ Data Returned:")
    print(json.dumps(res, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    test_specific_query()
