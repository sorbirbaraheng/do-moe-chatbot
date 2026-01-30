
import requests
import json
import time

# Configuration
API_URL = "http://127.0.0.1:5001/api/chat"
SESSION_ID = "collection_verifier_001"

# Map Collections to Test Questions
COLLECTION_TESTS = {
    "1. SCHOOLS (edu_schools_v5)": {
        "question": "ขอข้อมูลที่อยู่และพิกัดของโรงเรียนสวนกุหลาบวิทยาลัย",
        "expected_tool": "search_schools"
    },
    "2. TEACHERS (edu_teachers_v5)": {
        "question": "โรงเรียนเตรียมอุดมศึกษามีครูทั้งหมดกี่คน แยกตามประเภทให้หน่อย",
        "expected_tool": "count_teachers"
    },
    "3. STUDENTS (edu_students_v5)": {
        "question": "จังหวัดขอนแก่นมีนักเรียนชั้น ม.6 กี่คน แยกชายหญิงให้ด้วย",
        "expected_tool": "count_students"
    },
    "4. RATIOS (edu_ratios_v5)": {
        "question": "อัตราส่วนนักเรียนต่อครูของโรงเรียนบ้านบันนังลูวา คือเท่าไหร่",
        "expected_tool": "get_ratio"
    },
    "5. AREAS (edu_areas_v5)": {
        "question": "เขตพื้นที่การศึกษา สพป.เชียงใหม่ เขต 1 ดูแลกี่โรงเรียน",
        "expected_tool": "search_education_areas"
    },
    "6. GRADES (edu_grade_summary_v5)": {
        "question": "สรุปจำนวนนักเรียนแยกตามระดับชั้นของจังหวัดภูเก็ตให้หน่อย",
        "expected_tool": "get_grade_distribution"
    },
    "7. GENDER (edu_gender_overview_v5)": {
        "question": "สัดส่วนนักเรียนชายและหญิงของจังหวัดยะลาเป็นยังไง",
        "expected_tool": "analyze_gender_ratio"
    },
    "8. SYSTEMS (edu_systems_v5)": {
        "question": "จังหวัดปัตตานีมีโรงเรียนในระบบและนอกระบบอย่างละกี่แห่ง",
        "expected_tool": "count_by_system_type"
    }
}

def ns_timer():
    return time.time_ns()

def run_test():
    print(f"🚀 Starting Full Collection Verification...")
    print(f"🎯 Target: {API_URL}")
    print("=" * 60)

    results = {}
    
    for collection_name, test_data in COLLECTION_TESTS.items():
        q = test_data["question"]
        print(f"\n📂 Testing {collection_name}")
        print(f"❓ Question: {q}")
        
        start = ns_timer()
        try:
            response = requests.post(API_URL, json={
                "message": q,
                "history": [],
                "session_id": SESSION_ID,
                "category": "auto"
            }, timeout=45)
            
            duration_ms = (ns_timer() - start) / 1_000_000
            
            if response.status_code == 200:
                data = response.json()
                ans = data.get('response', '')
                
                # Check formatting/detail
                has_table = "|" in ans and "---" in ans
                has_numbers = any(c.isdigit() for c in ans)
                length = len(ans)
                
                print(f"✅ Response ({duration_ms:.0f}ms): {ans[:150]}...")
                print(f"   📊 Details: Length={length}, HasTable={has_table}, HasNumbers={has_numbers}")
                
                if length < 50:
                    print("   ⚠️ WARNING: Response seems too short/empty.")
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                print(response.text)
                
        except Exception as e:
            print(f"❌ Exception: {e}")
            
        time.sleep(2) # Cool down

if __name__ == "__main__":
    run_test()
