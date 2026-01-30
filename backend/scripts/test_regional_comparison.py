
import os
import sys
import logging
from dotenv import load_dotenv
from qdrant_client import QdrantClient

# Setup path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from chatbot.tool_executor import ToolExecutor

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load env (for Qdrant credentials if needed, though local usually doesn't need much)
load_dotenv()

def test_regional_comparison():
    print("🚀 Starting Regional Comparison Test...")
    
    # Initialize Client (Adjust host/port as per your local setup)
    # Using remote host from .env
    client = QdrantClient(url="http://203.159.242.144:6333")
    
    executor = ToolExecutor(client)
    
    # Test Cases
    test_cases = [
        ("ภาคเหนือ", "ภาคใต้", "schools"),  # Region vs Region
        ("เหนือ", "อีสาน", "students"),     # Alias vs Alias
        ("เชียงใหม่", "ภาคเหนือ", "schools") # Province vs Region (Mixed)
    ]
    
    for e1, e2, metric in test_cases:
        print(f"\n------------------------------------------------")
        print(f"🧪 Comparing: '{e1}' vs '{e2}' (Metric: {metric})")
        print(f"------------------------------------------------")
        
        try:
            result = executor._compare(e1, e2, metric)
            
            # Print simplified result
            d1 = result.get("entity1", {}).get("data", {})
            d2 = result.get("entity2", {}).get("data", {})
            
            val1 = d1.get("total") if d1 else "N/A"
            val2 = d2.get("total") if d2 else "N/A"
            
            type1 = d1.get("type", "unknown") if d1 else "unknown"
            type2 = d2.get("type", "unknown") if d2 else "unknown"
            
            print(f"✅ Result:")
            print(f"  {e1} ({type1}): {val1}")
            print(f"  {e2} ({type2}): {val2}")
            
            if d1 and d1.get("details"):
                 print(f"  Details {e1}: {d1.get('details')}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_regional_comparison()
