
import os
import sys
import logging
from dotenv import load_dotenv

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from chatbot.school_search import SchoolSearchEngine
from chatbot.llm_agent import MultiProviderLLM
from qdrant_client import QdrantClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_fuzzy_search():
    load_dotenv()
    
    # Initialize components
    # Use hardcoded URL or env, similar to web_chatbot_v5.py default
    qdrant_url = os.getenv("QDRANT_URL", "http://203.159.242.144:6333")
    client = QdrantClient(url=qdrant_url, timeout=10)
    
    print(f"🔌 Connecting to Qdrant at {qdrant_url}...")
    
    llm = MultiProviderLLM()
    search_engine = SchoolSearchEngine(client, llm_provider=llm)
    
    # Test cases: Misspelled names
    test_cases = [
        "รร.อนุบานปัตตานี",  # Typo: บาน -> บาล
        "วิทยลัยเทคนิค",      # Typo: วิทย -> วิทยา
        "เชียงหม่",          # Typo: หม่ -> ใหม่
        "บ้านหนองจิก"        # Ambiguous 
    ]
    
    print("\n" + "="*50)
    print("🚀 Testing Fuzzy Search Capabilities")
    print("="*50)
    
    for query in test_cases:
        print(f"\n🔎 Searching for: '{query}'")
        results = search_engine.search_by_name(query, limit=3)
        
        if results:
            print(f"✅ Found {len(results)} matches:")
            for i, res in enumerate(results):
                payload = res.payload.get('metadata', {})
                name = payload.get('school_name', 'Unknown')
                province = payload.get('province', 'Unknown')
                score = getattr(res, 'score', 0)
                print(f"   {i+1}. {name} ({province}) [Score: {score:.4f}]")
        else:
            print("❌ No matches found.")

if __name__ == "__main__":
    test_fuzzy_search()
