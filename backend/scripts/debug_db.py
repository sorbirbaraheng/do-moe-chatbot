from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchText

client = QdrantClient(host="203.159.242.144", port=6333)

print("🔎 Scroll search for 'ราชประชานุเคราะห์ 40'...")

try:
    response = client.scroll(
        collection_name="edu_schools_v5",
        scroll_filter=Filter(
            must=[
                FieldCondition(key="metadata.school_name", match=MatchText(text="ราชประชานุเคราะห์ 40"))
            ]
        ),
        limit=10,
        with_payload=True
    )

    results = response[0]
    print(f"Found {len(results)} exact matches for 'ราชประชานุเคราะห์ 40':")
    for r in results:
        print(f"- {r.payload.get('metadata', {}).get('school_name')}")

    print("\n🔎 Broad search for 'ราชประชานุเคราะห์' (MatchText)...")
    response_broad = client.scroll(
        collection_name="edu_schools_v5",
        scroll_filter=Filter(
            must=[
                FieldCondition(key="metadata.school_name", match=MatchText(text="ราชประชานุเคราะห์"))
            ]
        ),
        limit=50,
        with_payload=True
    )
    
    print("\n🔎 Searching 'edu_students_v5' for 'ราชประชานุเคราะห์ 40'...")
    response_student = client.scroll(
        collection_name="edu_students_v5",
        scroll_filter=Filter(
            must=[
                FieldCondition(key="metadata.school_name", match=MatchText(text="ราชประชานุเคราะห์ 40"))
            ]
        ),
        limit=10,
        with_payload=True
    )
    
    res_stu = response_student[0]
    print(f"Found {len(res_stu)} student records for 'ราชประชานุเคราะห์ 40':")
    for r in res_stu:
        print(f"- {r.payload.get('metadata', {}).get('school_name')}")

except Exception as e:
    print(f"❌ Error: {e}")
