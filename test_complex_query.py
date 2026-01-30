
import logging
import sys
import os

# Filter out annoying warnings
import warnings
warnings.filterwarnings("ignore")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from chatbot.chatbot_core import EducationChatbot
from chatbot.types import QueryIntent
from qdrant_client import QdrantClient

def test_complex_query():
    print("\n🚀 STARTING COMPLEX QUERY TEST...")
    
    # Initialize real backend
    try:
        # from config import QDRANT_HOST, QDRANT_PORT
        QDRANT_HOST = "203.159.242.144"
        QDRANT_PORT = 6333
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        bot = EducationChatbot(client)
        print("✅ Chatbot initialized")
    except Exception as e:
        print(f"❌ Failed to init chatbot: {e}")
        return

    # TEST CASE: "ขอข้อมูลโรงเรียนเตรียมอุดม" (Ambiguous)
    # Expects list of choices (Triam Udom Suksa, Triam Udom Pattanakarn, etc.)
    
    query = "ขอข้อมูลโรงเรียนเตรียมอุดม"
    print(f"\n👤 User: {query}")
    
    history = []
    response_gen = bot.chat(query, history)
    
    response_text = ""
    for h, r in response_gen:
        response_text = h[-1]['content']
        
    print(f"🤖 Bot: {response_text}")
    
    if "คุณหมายถึง" in response_text or "เลือก" in response_text or "หลายแห่ง" in response_text:
        print("✅ Seem to have understood criteria")
    else:
        print("❌ Failed to address the > 2000 criteria")

if __name__ == "__main__":
    test_complex_query()
