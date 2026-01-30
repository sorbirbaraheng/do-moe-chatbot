import sys
import os
import logging
from dotenv import load_dotenv

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from qdrant_client import QdrantClient
from chatbot.school_search import SchoolSearchEngine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    api_key = os.getenv("QDRANT_API_KEY")
    url = os.getenv("QDRANT_URL")
    
    if not url:
        print("❌ Missing QDRANT_URL")
        return

    qdrant_client = QdrantClient(url=url, api_key=api_key)
    engine = SchoolSearchEngine(qdrant_client)
    
    # Simulate the filter coming from ChatbotCore
    # Query: "โรงเรียนที่มีนักเรียนมากกว่า 1000 คนในปัตตานี"
    filters = {
        "province": "ปัตตานี",
        "min_students": 1000
    }
    
    print(f"\n--- Testing search_by_criteria with filters: {filters} ---")
    results, total, next_offset = engine.search_by_criteria(filters, limit=20)
    
    print(f"✅ Total Found: {total}")
    print(f"✅ Results Returned: {len(results)}")
    
    for hit in results:
        meta = hit.payload.get('metadata', {})
        print(f"- {meta.get('school_name')} (Students: {meta.get('total_students')}, Province: {meta.get('province')})")

if __name__ == "__main__":
    main()
