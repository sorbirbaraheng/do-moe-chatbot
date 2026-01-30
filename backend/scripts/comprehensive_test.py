
import requests
import json
import time

BASE_URL = "http://localhost:5001/api/chat"

# 15 Test Questions covering all collections and tools
TEST_CASES = [
    # --- SCHOOLS COLLECTION (Search & Details) ---
    {
        "category": "📍 School Location (Map)",
        "question": "โรงเรียนเตรียมอุดมอยู่ที่ไหนครับ",
        "expected_tool": "get_school_full_details"
    },
    {
        "category": "📞 Contact Info",
        "question": "ขอเบอร์โทรศัพท์โรงเรียนสวนกุหลาบวิทยาลัย",
        "expected_tool": "get_school_full_details"
    },
    
    # --- STUDENTS COLLECTION ---
    {
        "category": "👥 Student Count (School)",
        "question": "โรงเรียนสตรีวิทยามีนักเรียนทั้งหมดกี่คน",
        "expected_tool": "count_students"
    },
    {
        "category": "🚻 Student Gender (Province)",
        "question": "จังหวัดยะลามีนักเรียนชายกี่คน",
        "expected_tool": "count_students"
    },

    # --- TEACHERS COLLECTION ---
    {
        "category": "👨‍🏫 Teacher Count (Specific)",
        "question": "โรงเรียนบ้านบาเจาะมีครูกี่คนครับ",
        "expected_tool": "count_teachers"
    },
    {
        "category": "👩‍🏫 Teacher Count (Province)",
        "question": "ปัตตานีมีครูทั้งหมดกี่ท่าน",
        "expected_tool": "count_teachers"
    },

    # --- AREAS & AGENCIES ---
    {
        "category": "🏢 Education Area (Lookup)",
        "question": "สพป.เชียงใหม่ เขต 1 ครอบคลุมอำเภออะไรบ้าง",
        "expected_tool": "search_education_areas"
    },
    {
        "category": "📋 School List (Agency)",
        "question": "ขอรายชื่อโรงเรียนในสังกัด สพม.กรุงเทพมหานคร เขต 1 หน่อยครับ",
        "expected_tool": "list_schools"
    },

    # --- COMPARISONS & RANKING (Advanced) ---
    {
        "category": "🆚 Compare (School vs School)",
        "question": "เปรียบเทียบจำนวนนักเรียนโรงเรียนเตรียมอุดมกับสวนกุหลาบ",
        "expected_tool": "compare"
    },
    {
        "category": "🆚 Compare (Province)",
        "question": "เปรียบเทียบจำนวนครูในจังหวัดเชียงใหม่กับเชียงราย",
        "expected_tool": "compare"
    },
    {
        "category": "🏆 Ranking (Most)",
        "question": "5 อันดับโรงเรียนที่มีนักเรียนเยอะที่สุดในภูเก็ต",
        "expected_tool": "ranking"
    },
    {
        "category": "📉 Ranking (Least)",
        "question": "โรงเรียนที่มีนักเรียนน้อยที่สุด 5 อันดับใน กทม",
        "expected_tool": "ranking"
    },

    # --- RATIOS ---
    {
        "category": "⚖️ Student/Teacher Ratio",
        "question": "อัตราส่วนครูต่อนักเรียนของโรงเรียนหอวังเป็นเท่าไหร่",
        "expected_tool": "get_ratio"
    },

    # --- SYSTEMS (New Feature) ---
    {
        "category": "🏭 System Type",
        "question": "ในจังหวัดนราธิวาสมีโรงเรียนนอกระบบกี่แห่ง",
        "expected_tool": "count_by_system_type"  # If available, or count_schools fallback
    },

    # --- GENERAL KNOWLEDGE (LLM Fallback) ---
    {
        "category": "🧠 General Knowledge",
        "question": "ทำไมต้องเรียนลูกเสือครับ",
        "expected_tool": "general_knowledge" # or None (LLM direct)
    }
]

def run_tests():
    print(f"🚀 Starting Comprehensive System Test (15 Questions)\n")
    print(f"{'='*80}")
    
    passed = 0
    failed = 0
    
    for i, test in enumerate(TEST_CASES, 1):
        print(f"\n📝 Test {i}: {test['category']}")
        print(f"❓ Q: {test['question']}")
        
        start_time = time.time()
        try:
            # First request to init stream (or just simple POST if not streaming)
            # Assuming the backend supports simple POST at /api/chat similar to frontend
            # Actually frontend uses fetch('/api/chat', method: 'POST')
            
            payload = {
                "message": test['question'],
                "history": [],
                "config": {}  # Add dummy config if needed
            }
            
            response = requests.post(BASE_URL, json=payload, stream=True)
            
            if response.status_code == 200:
                print(f"✅ Status: 200 OK")
                
                # Consuming stream to get full text
                full_text = ""
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith("data: "):
                            try:
                                json_str = decoded_line[6:] # Strip "data: "
                                if json_str == "[DONE]": break
                                
                                data = json.loads(json_str)
                                if "content" in data:
                                    full_text += data["content"]
                            except:
                                pass
                
                # Simple validation check
                duration = time.time() - start_time
                print(f"⏱️ Time: {duration:.2f}s")
                print(f"📄 Response Preview: {full_text[:100]}...")
                
                # Check keywords to guess if tool worked
                if "ไม่พบข้อมูล" in full_text:
                    if test['expected_tool'] == "general_knowledge":
                         print("⚠️ Note: General Knowledge query returned generic fallback.")
                    else:
                         print("❌ Result: Possibly Data Not Found")
                else:
                    print("✅ Result: Data Found")
                
                passed += 1
            else:
                print(f"❌ Failed: Status {response.status_code}")
                print(response.text)
                failed += 1
                
        except Exception as e:
            print(f"❌ Error: {e}")
            failed += 1
            
        print(f"{'-'*80}")
        time.sleep(1) # Gentle delay
        
    print(f"\n📊 Test Summary: {passed}/{len(TEST_CASES)} Completed Successfully")

if __name__ == "__main__":
    run_tests()
