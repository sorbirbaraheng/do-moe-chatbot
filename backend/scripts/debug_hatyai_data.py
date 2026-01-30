import sys
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchText, MatchValue

client = QdrantClient(host="203.159.242.144", port=6333)


import re

def normalize_school_name(name):
    if not name: return name, None
    name = name.replace("โรงเรียน", "").replace("รร.", "").replace("วิทยาลัย", "").strip()
    extracted_grade = None
    grade_patterns = [
        (r'(ระดับ)?ประกาศนียบัตรวิชาชีพ(ชั้นสูง)?ปีที่\s*(\d+)', lambda m: f"ปวส.{m.group(3)}" if m.group(2) else f"ปวช.{m.group(3)}"),
        (r'(ระดับ)?ปวช\.?\s*(\d+)', lambda m: f"ปวช.{m.group(2)}"),
        (r'(ระดับ)?ปวส\.?\s*(\d+)', lambda m: f"ปวส.{m.group(2)}"),
        (r'(ระดับ)?ชั้น?มัธยมศึกษาปีที่\s*(\d+)', lambda m: f"ม.{m.group(2)}"),
        (r'(ระดับ)?ชั้น?ม\.?\s*(\d+)', lambda m: f"ม.{m.group(2)}"),
        (r'(ระดับ)?ชั้น?ประถมศึกษาปีที่\s*(\d+)', lambda m: f"ป.{m.group(2)}"),
        (r'(ระดับ)?ชั้น?ป\.?\s*(\d+)', lambda m: f"ป.{m.group(2)}"),
        (r'(ระดับ)?ชั้น?อนุบาล\s*(\d+)?', lambda m: f"อนุบาล{m.group(2) or ''}"),
    ]
    for pattern, extractor in grade_patterns:
        match = re.search(pattern, name)
        if match:
            extracted_grade = extractor(match)
            name = re.sub(pattern + r'.*$', '', name)
            break
    name = re.sub(r'(ระดับ)?ชั้น.*$', '', name)
    return name.strip(), extracted_grade

def normalize_grade(grade):
    if not grade: return grade
    grade = grade.strip()
    mapping = {
        "อ.1": "อนุบาล 1", "อ.2": "อนุบาล 2", "อ.3": "อนุบาล 3",
        "อนุบาล1": "อนุบาล 1", "อนุบาล2": "อนุบาล 2", "อนุบาล3": "อนุบาล 3",
        "ป.1": "ประถมศึกษาปีที่ 1", "ป.2": "ประถมศึกษาปีที่ 2", "ป.3": "ประถมศึกษาปีที่ 3",
        "ป.4": "ประถมศึกษาปีที่ 4", "ป.5": "ประถมศึกษาปีที่ 5", "ป.6": "ประถมศึกษาปีที่ 6",
        "ม.1": "มัธยมศึกษาปีที่ 1", "ม.2": "มัธยมศึกษาปีที่ 2", "ม.3": "มัธยมศึกษาปีที่ 3",
        "ม.4": "มัธยมศึกษาปีที่ 4", "ม.5": "มัธยมศึกษาปีที่ 5", "ม.6": "มัธยมศึกษาปีที่ 6",
        "ปวช.1": "ประกาศนียบัตรวิชาชีพปีที่ 1", "ปวช.2": "ประกาศนียบัตรวิชาชีพปีที่ 2", 
        "ปวช.3": "ประกาศนียบัตรวิชาชีพปีที่ 3",
        "ปวช1": "ประกาศนียบัตรวิชาชีพปีที่ 1", "ปวช2": "ประกาศนียบัตรวิชาชีพปีที่ 2",
        "ปวช3": "ประกาศนียบัตรวิชาชีพปีที่ 3",
        "ปวส.1": "ประกาศนียบัตรวิชาชีพชั้นสูงชั้นปีที่ 1", "ปวs.2": "ประกาศนียบัตรวิชาชีพชั้นสูงชั้นปีที่ 2",
        "ปวส1": "ประกาศนียบัตรวิชาชีพชั้นสูงชั้นปีที่ 1", "ปวส2": "ประกาศนียบัตรวิชาชีพชั้นสูงชั้นปีที่ 2",
    }
    for k, v in mapping.items():
        if k in grade or grade == k:
            return v
    return grade

def debug_hatyai():
    user_school_input = "วิทยาลัยเทคนิคหาดใหญ่"
    user_grade_input = "ปวส.1"
    
    norm_school, _ = normalize_school_name(user_school_input)
    norm_grade = normalize_grade(user_grade_input)
    
    print(f"Normalized School: '{norm_school}'")
    print(f"Normalized Grade: '{norm_grade}'")
    
    print("1. Testing MatchValue('ชาย')...")
    try:
        count_result = client.count(
            collection_name="edu_students_v5",
            count_filter=Filter(
                must=[
                    FieldCondition(key="metadata.school_name", match=MatchText(text=norm_school)),
                    FieldCondition(key="metadata.grade", match=MatchText(text=norm_grade)),
                    FieldCondition(key="metadata.gender", match=MatchValue(value="ชาย"))
                ]
            ),
            exact=True
        )
        print(f"MatchValue Result: {count_result.count}")
    except Exception as e:
        print(f"MatchValue Failed: {e}")

    print("2. Testing MatchText('ชาย')...")
    try:
        count_result = client.count(
            collection_name="edu_students_v5",
            count_filter=Filter(
                must=[
                    FieldCondition(key="metadata.school_name", match=MatchText(text=norm_school)),
                    FieldCondition(key="metadata.grade", match=MatchText(text=norm_grade)),
                    FieldCondition(key="metadata.gender", match=MatchText(text="ชาย"))
                ]
            ),
            exact=True
        )
        print(f"MatchText Result: {count_result.count}")
    except Exception as e:
        print(f"MatchText Failed: {e}")
    
    technical_college_id = None
    
    print("2. Fetching records to inspect 'count' field...")
    search_result = client.scroll(
        collection_name="edu_students_v5",
        scroll_filter=Filter(
            must=[
                FieldCondition(key="metadata.school_name", match=MatchText(text=norm_school)),
                FieldCondition(key="metadata.grade", match=MatchText(text=norm_grade))
            ]
        ),
        limit=20,
        with_payload=True
    )
    
    if search_result and search_result[0]:
        for point in search_result[0]:
            meta = point.payload.get('metadata', point.payload)
            name = meta.get('school_name', 'Unknown')
            sid = meta.get('school_id', 'Unknown')
            year = meta.get('year', 'Unknown')
            count_val = meta.get('count', 'N/A')
            gender_val = meta.get('gender', 'N/A')
            print(f"School: {name} | Year: {year} | Count: {count_val} | Gender: {gender_val}")
            
            if "เทคนิคหาดใหญ่" in name:
                technical_college_id = sid

    if not technical_college_id:
        print("❌ Could not find 'วิทยาลัยเทคนิคหาดใหญ่' in search results.")
        # Try finding exact name
        print("   Trying exact match for 'วิทยาลัยเทคนิคหาดใหญ่'...")
        search_result2 = client.scroll(
            collection_name="edu_schools_v5",
            scroll_filter=Filter(
                must=[FieldCondition(key="school_name", match=MatchText(text="วิทยาลัยเทคนิคหาดใหญ่"))]
            ),
            limit=5,
            with_payload=True
        )
        if search_result2 and search_result2[0]:
             for point in search_result2[0]:
                name = point.payload.get('school_name')
                sid = point.payload.get('school_id')
                print(f"   Found Exact: {name} (ID: {sid})")
                technical_college_id = sid

    if technical_college_id:
        print(f"\n2. Fetching student data for ID: {technical_college_id}...")
        # Get students
        students = client.scroll(
            collection_name="edu_students_v5",
            scroll_filter=Filter(
                must=[FieldCondition(key="school_id", match=MatchText(text=str(technical_college_id)))]
            ),
            limit=100,
            with_payload=True
        )
        
        if students and students[0]:
            print(f"Found {len(students[0])} student records:")
            for s in students[0]:
                meta = s.payload.get('metadata', s.payload) # Handle nested or flat
                grade = meta.get('grade', 'N/A')
                count = meta.get('count', 0)
                year = meta.get('year', 'N/A')
                print(f" - Grade: '{grade}' | Count: {count} | Year: {year}")
        else:
            print("❌ No student records found for this school ID.")

if __name__ == "__main__":
    debug_hatyai()
