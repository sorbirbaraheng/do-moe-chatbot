
import os
import sys
import logging
from dotenv import load_dotenv

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from qdrant_client import QdrantClient
from chatbot.search_engine import SearchEngine
from chatbot.constants import COLLECTION_NAMES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_search(engine, query: str, description: str):
    print(f"\n🧪 {description}")
    print(f"   Query: '{query}'")
    
    try:
        # Use _semantic_search directly to test the new collection
        results = engine._semantic_search(query, COLLECTION_NAMES["schools"], top_k=3)
        
        if not results:
            print("   ❌ No results found")
            return

        print(f"   ✅ Found {len(results)} results:")
        for i, res in enumerate(results, 1):
            meta = res.payload.get('metadata', {})
            score = res.score
            name = meta.get('school_name', 'Unknown')
            province = meta.get('province', 'Unknown')
            print(f"      {i}. {name} ({province}) [Score: {score:.4f}]")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()

def run_validation():
    print("🚀 Validating V6 Collection (Semantic Search)...")
    print(f"   Target Collection: {COLLECTION_NAMES['schools']}")
    
    # Initialize components
    qdrant_url = os.getenv('QDRANT_URL', 'http://203.159.242.144:6333')
    print(f"   Connecting to Qdrant at {qdrant_url}...")
    
    client = QdrantClient(url=qdrant_url)
    engine = SearchEngine(client=client)
    
    # 1. Typo / Partial Name
    test_search(engine, "รร บ้านหนองค้าง", "Testing Typo Handling (หนองคาง -> หนองค้าง)")
    
    # 2. Conceptual Search
    test_search(engine, "โรงเรียนที่สอนเด็กเล็กในเชียงใหม่", "Testing Conceptual Search (อนุบาล/เด็กเล็ก)")
    
    # 3. Location Semantic
    test_search(engine, "โรงเรียนแถวสยาม", "Testing Specific Location (สยาม)")

if __name__ == "__main__":
    run_validation()
