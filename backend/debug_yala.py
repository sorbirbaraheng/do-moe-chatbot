
import os
import sys
from qdrant_client import QdrantClient
from web_chatbot_v5 import SmartQueryParser, SchoolSearchEngine, COLLECTIONS
import logging

# Setup Logger
logging.basicConfig(level=logging.INFO)

# Setup Client
qdrant_client = QdrantClient(url="http://203.159.242.144:6333")
parser = SmartQueryParser()
engine = SchoolSearchEngine(qdrant_client)

# Target Query
query = "อยากรู้โรงเรียนที่อยู่อำเภอเมืองในจังหวัดยะลา"
print(f"Query: {query}")

# 1. Parse
parsed = parser.parse(query)
print(f"Parsed District: {parsed.district}")
print(f"Parsed Province: {parsed.province}")

# 2. Search
print("Searching...")
try:
    results = engine.search_by_district(parsed.province, parsed.district)
    print(f"Found {len(results)} results.")
    for res in results[:5]:
        meta = res.payload.get('metadata', {})
        print(f"- {meta.get('school_name')} (Dist: {meta.get('district')})")
except Exception as e:
    print(f"Error: {e}")
