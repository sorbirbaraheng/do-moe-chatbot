
import os
import sys
import logging
import json
from dotenv import load_dotenv
from qdrant_client import QdrantClient

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from chatbot.tool_executor import ToolExecutor
from chatbot.llm_agent import MultiProviderLLM

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_breakdown():
    load_dotenv()
    
    qdrant_url = os.getenv("QDRANT_URL", "http://203.159.242.144:6333")
    client = QdrantClient(url=qdrant_url, timeout=10)
    llm = MultiProviderLLM()
    
    executor = ToolExecutor(client, llm_provider=llm)
    
    school_name = "โรงเรียนสวนกุหลาบวิทยาลัย"
    print(f"🧪 Testing get_school_full_details for '{school_name}'...")
    
    result = executor.execute("get_school_full_details", {"school_name": school_name})
    
    if result.get("found"):
        print(f"✅ School Found: {result.get('school_name')}")
        breakdown = result.get("student_breakdown")
        
        if breakdown:
            print("✅ Student Breakdown Data Found:")
            print(json.dumps(breakdown, indent=2, ensure_ascii=False))
            
            # Simple validation
            grades_found = len(breakdown)
            total_students = sum(d['total'] for d in breakdown.values())
            print(f"📊 Summary: Found {grades_found} grades with {total_students} students.")
        else:
            print("❌ Student breakdown data is MISSING or EMPTY.")
            print("Raw result keys:", result.keys())
    else:
        print("❌ School search failed.")
        print(result)

if __name__ == "__main__":
    verify_breakdown()
