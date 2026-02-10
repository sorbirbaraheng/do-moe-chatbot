import json
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

client = QdrantClient(host="203.159.242.144", port=6333)

response = client.scroll(
    collection_name="edu_schools_v5",
    scroll_filter=Filter(
        must=[
            FieldCondition(key="metadata.province", match=MatchValue(value="ปัตตานี"))
        ]
    ),
    limit=10,
    with_payload=["metadata.total_teachers", "metadata.school_name"]
)

print(f"Found {len(response[0])} schools in Pattani (sample 10)")
for r in response[0]:
    payload = r.payload.get("metadata", {})
    print(f"- {payload.get('school_name')}: teachers={payload.get('total_teachers')}")
