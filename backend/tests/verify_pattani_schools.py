import sys
import os
import logging
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from chatbot.constants import PRIMARY_COLLECTION
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    # 1. Initialize Qdrant
    api_key = os.getenv("QDRANT_API_KEY")
    url = os.getenv("QDRANT_URL")
    
    if not url:
        print("❌ Missing QDRANT_URL")
        return

    client = QdrantClient(url=url, api_key=api_key)
    
    # 2. Construct Filter: Province=Pattani AND Students > 1000
    conditions = [
        FieldCondition(key="metadata.province", match=MatchValue(value="ปัตตานี")),
        FieldCondition(key="metadata.total_students", range=Range(gte=1000))
    ]
    
    query_filter = Filter(must=conditions)
    
    # 3. Count
    count_result = client.count(
        collection_name=PRIMARY_COLLECTION,
        count_filter=query_filter
    )
    
    print(f"✅ Total schools in Pattani with > 1000 students: {count_result.count}")
    
    # 4. List them to see names
    response = client.scroll(
        collection_name=PRIMARY_COLLECTION,
        scroll_filter=query_filter,
        limit=20,
        with_payload=True
    )
    
    print("\n--- School List ---")
    for point in response[0]:
        meta = point.payload.get('metadata', {})
        print(f"- {meta.get('school_name')} (Students: {meta.get('total_students')}, Agency: {meta.get('agency')})")

if __name__ == "__main__":
    # verify_firebase_config() 
    main()
