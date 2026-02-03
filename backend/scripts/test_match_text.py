
import os
import sys
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchText

load_dotenv()
client = QdrantClient(url=os.getenv("QDRANT_URL", "http://203.159.242.144:6333"))

print("🔍 Searching with MatchText (Full Text)...")

# Try "อาซิสสถาน"
query = "อาซิสสถาน"
print(f"\n📋 Query: {query}")
res = client.scroll(
    collection_name="edu_schools_v6",
    scroll_filter=Filter(
        must=[FieldCondition(key="metadata.school_name", match=MatchText(text=query))]
    ),
    limit=5,
    with_payload=True
)[0]
for r in res:
    print(f"   - MatchText: {r.payload.get('metadata', {}).get('school_name')}")

# Try "อาซิซสถาน" (Correct one)
query = "อาซิซสถาน"
print(f"\n📋 Query: {query}")
res = client.scroll(
    collection_name="edu_schools_v6",
    scroll_filter=Filter(
        must=[FieldCondition(key="metadata.school_name", match=MatchText(text=query))]
    ),
    limit=5,
    with_payload=True
)[0]
for r in res:
    print(f"   - MatchText: {r.payload.get('metadata', {}).get('school_name')}")
