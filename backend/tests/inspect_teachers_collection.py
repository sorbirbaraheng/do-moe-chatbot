import sys
import os
import logging
from dotenv import load_dotenv

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from qdrant_client import QdrantClient
from chatbot.constants import COLLECTIONS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    api_key = os.getenv("QDRANT_API_KEY")
    url = os.getenv("QDRANT_URL")
    
    if not url:
        print("❌ Missing QDRANT_URL")
        return

    client = QdrantClient(url=url, api_key=api_key)
    collection_name = COLLECTIONS["teachers"] # edu_teachers_v5
    
    print(f"📦 INSPECTING: {collection_name}")
    response = client.scroll(
        collection_name=collection_name,
        limit=5,
        with_payload=True
    )
    
    for point in response[0]:
        print("-" * 60)
        payload = point.payload
        # Sort keys for easier reading
        for k in sorted(payload.keys()):
            v = payload[k]
            if k == 'embedding': continue
            print(f"🔹 {k}: {v} (Type: {type(v).__name__})")

if __name__ == "__main__":
    main()
