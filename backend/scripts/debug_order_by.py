
from qdrant_client import QdrantClient
from qdrant_client.http import models

client = QdrantClient(host="203.159.242.144", port=6333)
coll = "edu_schools_v5"

try:
    res = client.scroll(
        collection_name=coll, 
        limit=5, 
        with_payload=True,
        order_by=models.OrderBy(key="metadata.total_students", direction="desc")
    )
    if res[0]:
        print("Success!")
        for pt in res[0]:
            print(f"{pt.payload['metadata']['school_name']}: {pt.payload['metadata']['total_students']}")
    else:
        print("No data")
except Exception as e:
    print(f"Error: {e}")
