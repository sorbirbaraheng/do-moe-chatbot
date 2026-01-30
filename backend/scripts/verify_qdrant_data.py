
import json
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchText

# Connect to Qdrant
client = QdrantClient(host="203.159.242.144", port=6333)
collection_name = "edu_schools_v5"

# List of schools from the screenshot to verify
target_schools = [
    "บ้านบันนังลูวา",
    "บ้านป่าพ้อ",
    "นิคมพัฒนวิทย์",
    "บ้านตาเนาะแมเราะ",
    "บ้านธารทิพย์",
    "จันทร์ประภัสสร์อนุสรณ์",
    "บ้านคูวอ",
    "มาดานีนุสรณ์",
    "นิคมสร้างตนเองธารโต 5",
    "บ้านแหร"
]

print(f"🔍 Verifying data for {len(target_schools)} schools in Yala...\n")
print(f"{'School Name':<30} | {'Students':<10} | {'Teachers':<10} | {'Calculated Ratio':<15}")
print("-" * 80)

for school_name in target_schools:
    # Try searching with "โรงเรียน" prefix first, then exact, then text match
    search_queries = [f"โรงเรียน{school_name}", school_name]
    
    found = False
    for q in search_queries:
        if found: break
        
        results = client.scroll(
            collection_name=collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="metadata.school_name", match=MatchText(text=q)),
                    FieldCondition(key="metadata.province", match=MatchValue(value="ยะลา"))
                ]
            ),
            limit=1
        )
        
        if results[0]:
            point = results[0][0]
            # Access nested metadata
            metadata = point.payload.get('metadata', {})
            db_school_name = metadata.get('school_name', '')
            
            # Double check it matches enough (simple check)
            if school_name not in db_school_name and db_school_name not in school_name:
                continue
                
            students = metadata.get('total_students', 0)
            teachers = metadata.get('total_teachers', 0)
            
            if teachers > 0:
                ratio = students / teachers
                ratio_str = f"{ratio:.1f}"
            else:
                ratio_str = "-"
                
            print(f"{db_school_name:<30} | {students:<10} | {teachers:<10} | {ratio_str:<15}")
            found = True
            
    if not found:
        print(f"{school_name:<30} | {'Not Found':<10} | {'-':<10} | {'-':<15}")

print("\n\nSample Record (Full Payload for first school):")
if target_schools:
     results = client.scroll(
        collection_name=collection_name,
        scroll_filter=Filter(
            must=[
                FieldCondition(key="school_name_th", match=MatchValue(value=target_schools[0])),
                FieldCondition(key="province_th", match=MatchValue(value="ยะลา"))
            ]
        ),
        limit=1
    )
     if results[0]:
        print(json.dumps(results[0][0].payload, indent=2, ensure_ascii=False))
