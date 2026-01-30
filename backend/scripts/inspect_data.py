
import os
import sys
import logging
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from chatbot.school_search import SchoolSearchEngine
from chatbot.llm_agent import MultiProviderLLM

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def inspect_student_data():
    load_dotenv()
    
    qdrant_url = os.getenv("QDRANT_URL", "http://203.159.242.144:6333")
    client = QdrantClient(url=qdrant_url, timeout=10)
    
    # Brute force search
    print(f"🔎 1. Brute forcing search for 'รัตนาธิเบศร์'...")
    
    response = client.scroll(
        collection_name="edu_schools_v6",
        scroll_filter=Filter(should=[
            FieldCondition(key="metadata.school_name", match=MatchValue(value="โรงเรียนรัตนาธิเบศร์")),
            FieldCondition(key="metadata.school_name", match=MatchValue(value="รัตนาธิเบศร์"))
        ]),
        limit=5,
        with_payload=True
    )
    
    if not response[0]:
        # Try finding anything with "รัตนาธิเบศร์" in text? (Qdrant doesn't do partial like SQL LIKE easily without text index)
        # Assuming exact match failed, let's try just listing first 5 schools to check connection
        print("❌ Exact match failed. Fetching first 5 schools to check data...")
        response = client.scroll(collection_name="edu_schools_v6", limit=5, with_payload=True)
        for p in response[0]:
             print(f"   - {p.payload.get('metadata', {}).get('school_name')}")
        return

    results = response[0]
    
    if results:
         school = results[0]
         school_payload = school.payload.get('metadata', {})
         school_id = school_payload.get('school_id')
         print(f"✅ Found School via Brute Force: {school_payload.get('school_name')} (ID: {school_id})")
    
    if not results or not school_id:
        print("❌ No School ID found in metadata!")
        return

    # 2. Find Student Data
    students_col = "edu_students_v5"
    print(f"\n🔎 2. Fetching Student Data for ID '{school_id}' in {students_col}...")
    
    response = client.scroll(
        collection_name=students_col,
        scroll_filter=Filter(must=[
            FieldCondition(key="metadata.school_id", match=MatchValue(value=str(school_id)))
        ]),
        limit=20,
        with_payload=True
    )
    
    students = response[0]
    if students:
        print(f"✅ Found {len(students)} student records.")
        
        # Analyze structure
        if students:
            print("First Record Metadata Keys:", students[0].payload.get('metadata', {}).keys())
            print("First Record Metadata Raw:", students[0].payload.get('metadata', {}))

        grades = set()
        total_students = 0
        
        for i, s in enumerate(students):
            meta = s.payload.get('metadata', {})
            # Try to guess keys based on raw print
            grade = meta.get('education_level') or meta.get('grade_level') or meta.get('level') or 'Unknown'
            count = meta.get('total') or meta.get('amount') or meta.get('student_count') or 0
            
            # Print raw if it's 0 to debug
            if i < 3:
                print(f"DEBUG Record #{i}: {meta}")

            grades.add(grade)
            try:
                total_students += int(count)
            except:
                pass
            
            # print(f"   - Grade: {grade}, Total: {count}")
            
        print(f"\n📊 Summary: {len(grades)} distinct grades, {total_students} total students found.")
    else:
        print("❌ No student records found for this ID.")

if __name__ == "__main__":
    inspect_student_data()
