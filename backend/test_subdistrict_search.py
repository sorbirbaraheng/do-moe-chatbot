
import os
import logging
from qdrant_client import QdrantClient
from chatbot.school_search import SchoolSearchEngine

# Configure logging
logging.basicConfig(level=logging.INFO)

# Configuration
QDRANT_URL = "http://203.159.242.144:6333"

def test_subdistrict_search():
    print(f"🔌 Connecting to Qdrant at {QDRANT_URL}...")
    try:
        client = QdrantClient(url=QDRANT_URL, timeout=10)
        engine = SchoolSearchEngine(client)
        
        print("\n🧪 Testing search_by_subdistrict('บานา', prov='ปัตตานี')...")
        results = engine.search_by_subdistrict(province="ปัตตานี", subdistrict="บานา")
        
        if results:
            print(f"✅ Success! Found {len(results)} schools in Tambon Bana.")
            for i, hit in enumerate(results[:5], 1):
                meta = hit.payload.get('metadata', {})
                print(f"  {i}. {meta.get('school_name')} (ต.{meta.get('subdistrict')} อ.{meta.get('district')})")
        else:
            print("❌ Failed: No schools found in Tambon Bana.")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_subdistrict_search()
