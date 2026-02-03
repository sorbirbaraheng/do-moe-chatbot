
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from chatbot.school_search import SchoolSearchEngine
from chatbot.tool_executor import ToolExecutor
from chatbot.llm_agent import MultiProviderLLM
import logging

logging.basicConfig(level=logging.INFO)

load_dotenv()

qdrant_url = os.getenv("QDRANT_URL", "http://203.159.242.144:6333")
client = QdrantClient(url=qdrant_url, timeout=10)

llm = MultiProviderLLM()
search = SchoolSearchEngine(client, llm_provider=llm)

print("=" * 70)
print("🔍 TESTING: โรงเรียนอาซิสสถาน")
print("=" * 70)

query_name = "อาซิสสถาน"
print(f"\n📋 Searching for: {query_name}")
print("-" * 50)

# 1. Exact/Smart Search
print("1. Smart Search Results:")
results = search.search_by_name(query_name, limit=5)
for i, r in enumerate(results[:5], 1):
    print(f"   {i}. {r['school_name']} (จ.{r['province']}) - Score: {r.get('score', 'N/A')}")

# 2. Semantic Search directly
print("\n2. Direct Semantic Search:")
import requests
embedding = llm.get_embedding(query_name)
search_result = client.search(
    collection_name="edu_schools_v6",
    query_vector=embedding,
    limit=5,
    with_payload=True
)

for i, r in enumerate(search_result, 1):
    print(f"   {i}. {r.payload.get('metadata', {}).get('school_name')} (จ.{r.payload.get('metadata', {}).get('province')}) - Score: {r.score}")

print("\n" + "=" * 70)
