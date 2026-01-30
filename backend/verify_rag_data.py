import os
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchText

# Configuration
QDRANT_URL = "http://203.159.242.144:6333"
COLLECTION_SCHOOLS = "edu_schools_v5"

# Entities to verify from the test plan
SCHOOLS_TO_CHECK = [
    "เตรียมอุดมศึกษา", 
    "สตรีวิทยา", 
    "สวนกุหลาบวิทยาลัย", 
    "สามเสนวิทยาลัย"
]

LOCATIONS_TO_CHECK = [
    {"type": "province", "name": "ยะลา"},
    {"type": "province", "name": "ปัตตานี"},
    {"type": "district", "name": "หาดใหญ่"}, # สงขลา
    {"type": "province", "name": "เชียงใหม่"},
    {"type": "province", "name": "เชียงราย"},
    {"type": "subdistrict", "name": "บานา"}, # ปัตตานี
]

def verify_data():
    print(f"🔌 Connecting to Qdrant at {QDRANT_URL}...")
    try:
        client = QdrantClient(url=QDRANT_URL, timeout=10)
        collections = client.get_collections()
        collection_names = [c.name for c in collections.collections]
        
        print(f"✅ Connected! Found {len(collection_names)} collections.")
        if COLLECTION_SCHOOLS not in collection_names:
            print(f"❌ Critical Error: Collection '{COLLECTION_SCHOOLS}' not found!")
            return

        print(f"\n🏫 Verifying Schools in '{COLLECTION_SCHOOLS}':")
        for school_name in SCHOOLS_TO_CHECK:
            # Try fuzzy search first (MatchText)
            results = client.scroll(
                collection_name=COLLECTION_SCHOOLS,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="metadata.school_name",
                            match=MatchText(text=school_name)
                        )
                    ]
                ),
                limit=1,
                with_payload=True
            )[0]
            
            if results:
                found_name = results[0].payload['metadata']['school_name']
                print(f"  ✅ Found '{school_name}' -> Matches '{found_name}'")
            else:
                print(f"  ❌ NOT FOUND: '{school_name}'")

        print(f"\n📍 Verifying Locations in '{COLLECTION_SCHOOLS}':")
        for loc in LOCATIONS_TO_CHECK:
            key = f"metadata.{loc['type']}"
            value = loc['name']
            
            # Check existence by counting (limit=1)
            results = client.scroll(
                collection_name=COLLECTION_SCHOOLS,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key=key,
                            match=MatchValue(value=value)
                        )
                    ]
                ),
                limit=1,
                with_payload=False
            )[0]
            
            if results:
                print(f"  ✅ Found {loc['type']} '{value}' (Data exists)")
            else:
                print(f"  ❌ NOT FOUND: {loc['type']} '{value}'")

    except Exception as e:
        print(f"❌ Error verifying data: {e}")

if __name__ == "__main__":
    verify_data()
