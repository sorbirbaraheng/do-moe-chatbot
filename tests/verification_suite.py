
import requests
import json
import time
import sys

# Configuration
API_URL = "http://127.0.0.1:5001/api/chat"
SESSION_ID = "ai_engineer_test_001"

# Test Cases: Category -> List of Questions
TEST_CASES = {
    "TYPE_1_PURE_LLM_ANALYTICAL": [
        "อัตราการเกิดน้อยของเด็กมีผลไหมต่อการศึกษาในอนาคต",  # Analytical
        "เด็กยุคใหม่สมาธิสั้นลง จริงไหม และครูควรปรับการสอนยังไงดี", # User's Challenge Question
        "ทำไมครูถึงลาออกเยอะจัง วิเคราะห์ให้หน่อย"           # Opinion/Synthesis
    ],
    "TYPE_2_RAG_PROCEDURAL": [
        "ขั้นตอนการกรอกข้อมูลในระบบ DMC ทำยังไง",           # How-to (Needs RAG)
        "เงินอุดหนุนรายหัวนักเรียนปี 2567 ได้เท่าไหร่",        # Factoids (Needs RAG)
    ],
    "TYPE_3_DATABASE_QUANTITATIVE": [
        "โรงเรียนเตรียมอุดมศึกษา มีครูทั้งหมดกี่คน",             # Specific School Data
        "จังหวัดเชียงใหม่มีโรงเรียนกี่แห่ง",                   # Non-Yala Province Check
        "ขอนแก่นมีนักเรียนกี่คน",                            # Non-Yala Student Check
    ],
    "TYPE_5_AMBIGUOUS_CHALLENGE": [
        "โรงเรียนวัด",                                     # Ambiguous
        "หาข้อมูลรร.สวนกุหลาบวิทยาลัย",                      # Abbreviation prefix check
        "เทพศิรินทร์มีครูกี่คน",                              # No Prefix check (Fuzzy/Hybrid)
        "จังหวัดยะลามีสัดส่วนนักเรียนต่อครูเท่าไหร่",           # Complex Ratio
    ]
}

def run_test():
    print(f"🚀 Starting AI Engineer Verification Suite...")
    print(f"🎯 Target: {API_URL}")
    print("=" * 60)

    results = {}

    for category, questions in TEST_CASES.items():
        print(f"\n📂 Testing Category: {category}")
        for q in questions:
            print(f"\n❓ Question: {q}")
            start_time = time.time()
            try:
                response = requests.post(API_URL, json={
                    "message": q,
                    "history": [],
                    "session_id": SESSION_ID,
                    "category": "auto" # Force auto-detection
                }, timeout=30)
                
                duration = time.time() - start_time
                
                if response.status_code == 200:
                    data = response.json()
                    ans = data.get('response', '')
                    # Heuristic analysis of response type
                    response_type = "UNKNOWN"
                    if "QUOTA_EXCEEDED" in ans:
                        response_type = "ERROR_QUOTA"
                    elif "โรงเรียน" in ans and any(c.isdigit() for c in ans):
                        response_type = "DATABASE_LIKELY"
                    elif "ขั้นตอน" in ans or "ระเบียบ" in ans:
                        response_type = "RAG_LIKELY"
                    elif len(ans) > 200:
                        response_type = "LLM_LIKELY"
                    
                    print(f"✅ Response ({duration:.2f}s): {ans[:100]}...")
                    print(f"🕵️  Detected Type: {response_type}")
                else:
                    print(f"❌ HTTP Error: {response.status_code}")
                    print(response.text)
            except Exception as e:
                print(f"❌ Exception: {e}")
            
            time.sleep(1) # Prevent rate limiting

if __name__ == "__main__":
    run_test()
