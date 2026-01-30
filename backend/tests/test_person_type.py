import sys
import os
import logging
from dotenv import load_dotenv

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from chatbot.query_parser import SmartQueryParser

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    parser = SmartQueryParser(qdrant_client=None)
    
    test_queries = [
        "โรงเรียนบ้านสะบารังมีลูกจ้างชั่วคราวกี่คน",
        "พนักงานราชการในจังหวัดปัตตานีมีกี่คน",
        "ครูอัตราจ้างในโรงเรียนบ้านมดตะนอย"
    ]
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        
        parsed = parser.parse(query)
        print(f"  - person_type: {parsed.person_type}")
        print(f"  - school_name: {parsed.school_name}")
        print(f"  - province: {parsed.province}")

if __name__ == "__main__":
    main()
