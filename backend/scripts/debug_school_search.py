
import sys
import os
import json
import logging
from unittest.mock import MagicMock

# Add backend directory to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

# We need to setup Qdrant client connection real or mock? 
# The user wants to debug why it's not showing, so we likely need REAL data.
# But checking connection might be hard if environment variables aren't set in this shell.
# However, the previous `test_map_generation.py` used mocks. 
# To debug "why map not showing" for a specific data point, I need to know what Data is in Qdrant.
# I will try to use the ToolExecutor logic which uses the real Qdrant connection if available.

from chatbot.chatbot_core import EducationChatbot
# chatbot_core initializes everything.

def debug_search():
    print("🔍 Debugging Search for 'โรงเรียนเทศบาล 4 วัดนพวงศาราม'...")
    
    try:
        # Initialize Chatbot (which connects to Qdrant)
        from qdrant_client import QdrantClient
        
        # Hardcoded for debugging based on web_chatbot_v5.py default or usage
        QDRANT_URL = "http://203.159.242.144:6333" 
        client = QdrantClient(url=QDRANT_URL, timeout=10)
        
        chatbot = EducationChatbot(qdrant_client=client)
        
        query = "โรงเรียนเทศบาล 4 วัดนพวงศาราม"
        
        # 1. Test standard search
        print(f"\n[1] Executing _smart_search_school('{query}')...")
        results = chatbot.llm_agent.tool_executor._smart_search_school(query, limit=10)
        
        print(f"Found {len(results)} matches.")
        for i, res in enumerate(results):
            payload = res.payload
            meta = payload.get('metadata', {})
            name = meta.get('school_name', 'N/A')
            lat = meta.get('latitude')
            lon = meta.get('longitude')
            score = getattr(res, 'score', 0)
            print(f"  {i+1}. {name} (Score: {score:.4f})")
            print(f"     Lat: {lat}, Lon: {lon}")
            print(f"     Province: {meta.get('province')}")
            print(f"     Full Metadata: {meta}")
            
        # 2. Test ambiguity resolution logic - REMOVED for clarity
        # print("\n[2] Testing _resolve_school_ambiguity...")
        # resolution = chatbot.llm_agent.tool_executor._resolve_school_ambiguity(query)
        # print(f"Resolution Type: {resolution.get('type')}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_search()
