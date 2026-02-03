
import os
import sys
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

load_dotenv()
client = QdrantClient(url=os.getenv("QDRANT_URL", "http://203.159.242.144:6333"))

print("🔍 Listing schools in Pattani to spot 'Aziz' variants...")

schools, _ = client.scroll(
    collection_name="edu_schools_v6",
    scroll_filter=Filter(
        must=[
            FieldCondition(key="metadata.province", match=MatchValue(value="ปัตตานี"))
        ]
    ),
    limit=500,
    with_payload=True
)

found_variants = []
for s in schools:
    name = s.payload.get("school_name", "")
    if "อา" in name and "ส" in name:  # Very broad filter
        found_variants.append(name)

print(f"found {len(found_variants)} candidates containing 'อา' + 'ส'")
for name in found_variants:
    print(f" - {name}")
