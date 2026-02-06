
import os
import sys
from dotenv import load_dotenv
from qdrant_client import QdrantClient

# Load env (adjust path if needed)
load_dotenv("./backend/.env")

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
print(f"Connecting to {QDRANT_URL}...")
client = QdrantClient(url=QDRANT_URL)

def check_school():
    school_name = "ตันหยงมัส"
    print(f"Searching for {school_name}...")
    
    # 1. Search in schools collection using scroll
    from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchText
    
    response = client.scroll(
        collection_name="edu_schools_v6",
        scroll_filter=Filter(
            should=[
                FieldCondition(key="metadata.school_name", match=MatchText(text=school_name)),
                FieldCondition(key="metadata.school_name", match=MatchValue(value=school_name))
            ]
        ),
        limit=10,
        with_payload=True
    )
    
    points, _ = response
    print(f"Found {len(points)} schools.")
    
    for p in points:
        meta = p.payload.get('metadata', {})
        name = meta.get('school_name')
        teachers = meta.get('total_teachers')
        students = meta.get('total_students')
        print(f"School: {name}")
        print(f" - Teachers: {teachers}")
        print(f" - Students: {students}")
        print(f" - Province: {meta.get('province')}")
        print(f" - District: {meta.get('district')}")
        print("-" * 20)

if __name__ == "__main__":
    check_school()
