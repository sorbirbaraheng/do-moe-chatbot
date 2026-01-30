
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

# Connect to Qdrant
client = QdrantClient(host="203.159.242.144", port=6333)
collection_name = "edu_schools_v5"

print("🔍 Listing first 50 schools in Yala...")
print("-" * 80)

# Try simple filter first
try:
    results = client.scroll(
        collection_name=collection_name,
        scroll_filter=Filter(
            must=[
                FieldCondition(key="province_th", match=MatchValue(value="ยะลา"))
            ]
        ),
        limit=50
    )
    
    if results[0]:
        for point in results[0]:
            p = point.payload
            print(f"Name: {p.get('school_name_th')} | Prov: {p.get('province_th')} | Std: {p.get('total_students')} | Tch: {p.get('total_teachers')}")
    else:
        print("❌ No schools found for province 'ยะลา'. Trying 'จ.ยะลา'...")
        # Try variation
        results = client.scroll(
            collection_name=collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="province_th", match=MatchValue(value="จ.ยะลา"))
                ]
            ),
            limit=10
        )
        if results[0]:
            for point in results[0]:
                p = point.payload
                print(f"Name: {p.get('school_name_th')} | Prov: {p.get('province_th')}")
        else:
            print("❌ Still not found. Listing ANY school to check format...")
            results = client.scroll(collection_name=collection_name, limit=5)
            for point in results[0]:
                 print(f"Sample: {point.payload}")

except Exception as e:
    print(f"Error: {e}")
