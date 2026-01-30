
import logging
from backend.chatbot.chatbot_core import EducationChatbot

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from qdrant_client import QdrantClient
import os

def test_drilldown():
    print("\n🚀 STARTING LIVE DRILL-DOWN TEST...\n")
    
    # Initialize Qdrant Client (Mocking functionality from web_chatbot_v5.py)
    QDRANT_URL = os.getenv("QDRANT_URL", "http://203.159.242.144:6333")
    client = QdrantClient(url=QDRANT_URL, timeout=10)
    
    # Initialize Chatbot
    bot = EducationChatbot(client)
    history = []
    
    # 1. Ask for Total Teachers (Establishes Context)
    q1 = "โรงเรียนยุพราชวิทยาลัยมีครูกี่คน"
    print(f"👤 User: {q1}")
    response_gen1 = bot.chat(q1, history)
    resp1 = ""
    for r, _ in response_gen1:
        if r:
            resp1 = r[-1]['content']
    print(f"🤖 Bot: {resp1}\n")
    
    # Update history correctly (chat method updates it internally usually, but for simulate let's trust the return)
    # Actually bot.chat returns the updated history list
    history.append({"role": "user", "content": q1})
    history.append({"role": "assistant", "content": resp1})
    
    # 2. Ask for Female Teachers (Uses Context)
    q2 = "มีครูผู้หญิงกี่คน"
    print(f"👤 User: {q2}")
    response_gen2 = bot.chat(q2, history)
    resp2 = ""
    for r, _ in response_gen2:
        if r:
            resp2 = r[-1]['content']
    print(f"🤖 Bot: {resp2}\n")
    
    # Update history
    history.append({"role": "user", "content": q2})
    history.append({"role": "assistant", "content": resp2})
    
    # 3. Ask for specific Person Type (Deep Filter)
    q3 = "มีลูกจ้างชั่วคราวกี่คน"
    print(f"👤 User: {q3}")
    response_gen3 = bot.chat(q3, history)
    resp3 = ""
    for r, _ in response_gen3:
        if r:
            resp3 = r[-1]['content']
    print(f"🤖 Bot: {resp3}\n")

if __name__ == "__main__":
    test_drilldown()
