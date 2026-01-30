
import os
import sys

# Add backend directory to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from chatbot.chatbot_core import EducationChatbot
from qdrant_client import QdrantClient
from qdrant_client.http import models

def test_search():
    # Initialize Qdrant Client
    qdrant_url = os.getenv("QDRANT_URL", "http://203.159.242.144:6333")
    client = QdrantClient(url=qdrant_url)
    
    # Initialize chatbot with client
    bot = EducationChatbot(qdrant_client=client)
    
    query = "บาเจาะ"
    print(f"🔍 Searching for '{query}' directly in Qdrant...")
    
    # 1. Try Vector Search via _smart_search_school logic
    # But let's just do a direct scroll/filter to be sure
    
    # Filter for names containing "บาเจาะ"
    condition = models.Filter(
        must=[
            models.FieldCondition(
                key="metadata.school_name", 
                match=models.MatchText(text=query)
            )
        ]
    )
    
    results = bot.qdrant_client.scroll(
        collection_name=bot.collections["schools"],
        scroll_filter=condition,
        limit=10
    )
    
    print(f"✅ Found {len(results[0])} matches via Text Match:")
    for point in results[0]:
        print(f"- {point.payload.get('metadata', {}).get('school_name')} (ID: {point.id})")

if __name__ == "__main__":
    test_search()
