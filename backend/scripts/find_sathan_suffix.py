
import os
import sys
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
import json

load_dotenv()
client = QdrantClient(url=os.getenv("QDRANT_URL", "http://203.159.242.144:6333"))

print("🔍 Searching for schools ending with 'สถาน' in Pattani...")

res = client.scroll(
    collection_name="edu_schools_v6",
    scroll_filter=Filter(
        must=[FieldCondition(key="metadata.province", match=MatchValue(value="ปัตตานี"))],
    ),
    limit=500,
    with_payload=True
)[0]

found = []
for r in res:
    name = r.payload.get('metadata', {}).get('school_name', '')
    if "สถาน" in name:
        found.append(name)

if found:
    for f in found:
        print(f" - {f}")
else:
    print("❌ No matches")
