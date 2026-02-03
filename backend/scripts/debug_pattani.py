
import os
import sys
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

load_dotenv()
client = QdrantClient(url=os.getenv("QDRANT_URL", "http://203.159.242.144:6333"))

print("🔍 Debugging Pattani Schools...")

# 1. Count Total
count = client.count(
    collection_name="edu_schools_v6",
    count_filter=Filter(
        must=[FieldCondition(key="metadata.province", match=MatchValue(value="ปัตตานี"))]
    )
)
print(f"📊 Total Schools in Pattani: {count.count}")

# 2. List Sample
print("\n📋 Sample 10 Schools:")
res = client.scroll(
    collection_name="edu_schools_v6",
    scroll_filter=Filter(
        must=[FieldCondition(key="metadata.province", match=MatchValue(value="ปัตตานี"))]
    ),
    limit=10,
    with_payload=True
)[0]

for r in res:
    print(f"   - {r.payload.get('school_name')}")
