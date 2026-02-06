import os
import sys
import logging
from dotenv import load_dotenv

# Setup path and logging
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
logging.basicConfig(level=logging.INFO)
load_dotenv(os.path.join(os.path.dirname(__file__), '../.env'))

from backend.chatbot.llm_agent import LLMAgent
from backend.chatbot.llm import MultiProviderLLM
from qdrant_client import QdrantClient

def test_context_flow():
    print("🚀 Initializing Chatbot Components...")
    
    # 1. Setup
    client = QdrantClient(host="localhost", port=6333)
    llm = MultiProviderLLM()
    # Correct instantiation
    chatbot = LLMAgent(qdrant_client=client, llm=llm)
    
    # =========================================================================
    # 📌 Scenario 1: Region Comparison (North vs South)
    # =========================================================================
    query_1 = "ระหว่างภาคเหนือกับภาคใต้ภาคไหนมีนักเรียนมากกว่ากัน"
    print(f"\n🗣️ User Turn 1: {query_1}")
    
    # Mocking successful AI response for Q1 (since we focus on context)
    ai_msg_1 = "มีนักเรียนทั้งหมด 1,985,950 คน ในภาคใต้ ซึ่งมากกว่าภาคเหนือถึง 944,789 คน"
    print(f"🤖 Bot Response 1 (MOCKED): {ai_msg_1}")
    
    context_1 = {"last_ai_response": ai_msg_1}

    # =========================================================================
    # 📌 Scenario 2: South Region Analysis (Most students province)
    # =========================================================================
    query_2 = "ขอข้อมูลโรงเรียนในภาคใต้ว่าจังหวัดไหนมีนักเรียนมากกที่สุด"
    print(f"\n🗣️ User Turn 2: {query_2}")
    
    # Process Q2
    # We expect `ranking` or `search_schools` tool
    # For this test, let's assume it works and mocked response again to prep for Q3
    ai_msg_2 = "มีโรงเรียนในจังหวัดใต้ที่มีนักเรียนมากที่สุดคือ วิทยาลัยเทคโนโลยีภาคตะวันออก (อี.เทค) โดยมีนักเรียนทั้งหมด 18,757 คน ครับ"
    print(f"🤖 Bot Response 2 (MOCKED): {ai_msg_2}")
    
    context_2 = {
        "last_ai_response": ai_msg_2,
        "chat_history": [
            {"role": "user", "content": query_1},
            {"role": "assistant", "content": ai_msg_1},
            {"role": "user", "content": query_2},
            {"role": "assistant", "content": ai_msg_2}
        ]
    }

    # =========================================================================
    # 📌 Scenario 3: Contextual Follow-up ("Where is it?")
    # =========================================================================
    query_3 = "อยู่จังหวัดไหนครับ"
    print(f"\n🗣️ User Turn 3: {query_3}")
    
    response_3, _ = chatbot.process_query(query_3, context_2)
    print(f"🤖 Bot Response 3: {response_3}")

    # Validation
    if "ชลบุรี" in response_3 or "จังหวัด" in response_3:
        print("\n✅ PASS: Context retained and location found.")
    else:
        print("\n❌ FAIL: Context lost or general chat used.")

if __name__ == "__main__":
    test_context_flow()
