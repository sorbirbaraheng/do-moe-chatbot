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
    
    query = "โรงเรียนที่มีนักเรียนมากกว่า 1000 คนในปัตตานี"
    print(f"Query: {query}")
    
    # 1. Test LLM Extraction Separately
    print("\n--- LLM Extraction ---")
    llm_entities = parser._extract_entities_llm(query)
    print(f"LLM Entities: {llm_entities}")
    
    # 2. Test Legacy Extraction (simulated, as it's private/internal usually, 
    # but we can infer from proper parse)
    
    # We can inspect the 'parse' method logic by running it and checking logs, 
    # or by importing the NER component if it exists. 
    # SmartQueryParser seems to use regex/keywords internally or a helper?
    # Let's check 'entities' passed to ParsedQuery
    
    print("\n--- Full Parse ---")
    parsed = parser.parse(query)
    print(f"Final Parsed District: '{parsed.district}'")
    
    # 3. Check if 'มากกว่า' allows being a district
    # If it's a legacy match, it might be in THAI_PROVINCES or constants? 
    # Or just a keyword proximity issue.

if __name__ == "__main__":
    main()
