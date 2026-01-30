
from qdrant_client import QdrantClient

client = QdrantClient(host="203.159.242.144", port=6333)
coll = "edu_schools_v5"

res = client.scroll(collection_name=coll, limit=1, with_payload=True)
if res[0]:
    print(res[0][0].payload)
else:
    print("No data")
