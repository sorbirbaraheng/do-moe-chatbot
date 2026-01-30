
import os
import sys
import logging
import json
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchText

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from chatbot.constants import COLLECTION_NAMES

def inspect_school(school_name):
    qdrant_url = os.getenv('QDRANT_URL', 'http://203.159.242.144:6333')
    client = QdrantClient(url=qdrant_url)
    
    print(f"🔍 Searching for '{school_name}' in {COLLECTION_NAMES['schools']}...")
    
    response = client.scroll(
        collection_name=COLLECTION_NAMES["schools"],
        scroll_filter=Filter(must=[
            FieldCondition(key="metadata.school_name", match=MatchText(text=school_name))
        ]),
        limit=5,
        with_payload=True
    )
    
    results = response[0]
    if not results:
        print("❌ No results found in schools collection.")
        return

    for res in results:
        meta = res.payload.get('metadata', {})
        print(f"\n🏫 Found: {meta.get('school_name')} (ID: {meta.get('school_id')})")
        print(f"   Province: {meta.get('province')}")
        print(f"   Total Students (in metadata): {meta.get('total_students')}")
        print(f"   Total Teachers (in metadata): {meta.get('total_teachers')}")
        print(f"   Payload Keys: {list(meta.keys())}")

        # Also check students collection if ID exists
        school_id = meta.get('school_id')
        if school_id:
            print(f"   -------- Checking {COLLECTION_NAMES['students']} for ID {school_id} --------")
            try:
                stud_res = client.scroll(
                    collection_name=COLLECTION_NAMES["students"],
                    scroll_filter=Filter(must=[
                        FieldCondition(key="metadata.school_id", match=MatchText(text=school_id))
                    ]),
                    limit=1,
                    with_payload=True
                )
                if stud_res[0]:
                    stud_meta = stud_res[0][0].payload.get('metadata', {})
                    print(f"   Student Collection Record found:")
                    print(f"   Total Students: {stud_meta.get('total_students')}")
                    print(f"   Stats: {json.dumps(stud_meta.get('student_stats', {}), indent=2, ensure_ascii=False)}")
                else:
                    print(f"   ❌ No record found in students collection for ID {school_id}")
            except Exception as e:
                print(f"   error checking students: {e}")

if __name__ == "__main__":
    inspect_school("บำรุงอิสลาม")
