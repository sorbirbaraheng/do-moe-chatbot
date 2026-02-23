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

def test_reflection():
    print("🚀 Initializing Test with Reflection...")
    qdrant = _get_qdrant_client()
    llm = MultiProviderLLM()
    agent = LLMAgent(qdrant, llm)
    
    # Query with a non-existent district to force an empty result
    # We expect the agent to first query district="อำเภอบางบ่อ" (which doesn't exist in Chiang Mai)
    # Then fail, retry with the reflection prompt, and hopefully drop or broaden the district.
    test_query = "โรงเรียนในอำเภอบางบ่อ จังหวัดเชียงใหม่ มีกี่แห่ง"
    
    print(f"\n❓ Question: {test_query}\n")
    response, active_query = agent.process_query(test_query)
    
    print("\n✅ Final Response:")
    print(response)
    print("\n🔍 Active Query Params:")
    print(active_query)

if __name__ == "__main__":
    test_reflection()
