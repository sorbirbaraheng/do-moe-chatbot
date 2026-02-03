
import os
import sys
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
import json

load_dotenv()
client = QdrantClient(url=os.getenv("QDRANT_URL", "http://203.159.242.144:6333"))

print("🔍 Dumping Payload Structure...")

res = client.scroll(
    collection_name="edu_schools_v6",
    limit=1,
    with_payload=True
)[0]

if res:
    print(json.dumps(res[0].payload, ensure_ascii=False, indent=2))
else:
    print("❌ No data found")
