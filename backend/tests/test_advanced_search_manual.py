import sys
import os
import logging
from typing import Dict, Any

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from chatbot.chatbot_core import EducationChatbot
from chatbot.query_parser import SmartQueryParser

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_extraction(parser: SmartQueryParser, query: str):
    print(f"\n--- Testing Query: '{query}' ---")
    parsed = parser.parse(query)
    print(f"Intent: {parsed.intent}")
    # print(f"Entities: {parsed.entities}") # 'entities' field removed from dataclass
    print(f"New Fields: min_students={parsed.min_students}, area_name={parsed.area_name}")
    print(f"Location: province={parsed.province}, district={parsed.district}")
    return parsed

def main():
    # Instantiate Parser directly (mocking qdrant as None since we only test LLM extraction)
    parser = SmartQueryParser(qdrant_client=None)
    
    # 1. Test Student Count Extraction
    q1 = "โรงเรียนที่มีนักเรียนมากกว่า 1000 คนในปัตตานี"
    parsed1 = test_extraction(parser, q1)
    
    # 2. Test Area Name Extraction
    q2 = "โรงเรียนในสังกัด สพป.ปัตตานี เขต 1"
    parsed2 = test_extraction(parser, q2)
    
    # 3. Test Teacher Count + Province
    q3 = "หาโรงเรียนในยะลาที่มีครูน้อยกว่า 10 คน"
    parsed3 = test_extraction(parser, q3)

if __name__ == "__main__":
    main()
