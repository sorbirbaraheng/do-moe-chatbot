
import requests
import json
import time

# Configuration
API_URL = "http://127.0.0.1:5001/api/chat"
SESSION_ID = "user_fix_verification"

# Specific User Issues
TEST_CASES = [
    {
        "description": "User Issue 1: 'รร.' prefix search failed",
        "question": "ขอพิกัด รร.สวนกุหลาบ",
        "expected_keywords": ["พิกัด", "13.", "100."] 
    },
    {
        "description": "User Issue 2: Grade breakdown returned only total",
        "question": "สรุปจำนวนนักเรียนเชียงใหม่ แยกตามระดับชั้นให้หน่อย",
        "expected_keywords": ["|", "ป.1", "ม.6", "ตาราง"]
    }
]

def run_test():
    print(f"🚀 Starting User Issue Verification...")
    print(f"🎯 Target: {API_URL}")
    print("=" * 60)

    for test in TEST_CASES:
        q = test["question"]
        print(f"\n📂 Testing: {test['description']}")
        print(f"❓ Question: {q}")
        
        try:
            start = time.time()
            response = requests.post(API_URL, json={
                "message": q,
                "history": [],
                "session_id": SESSION_ID,
                "category": "auto"
            }, timeout=30)
            duration = time.time() - start
            
            if response.status_code == 200:
                data = response.json()
                ans = data.get('response', '')
                
                print(f"✅ Response ({duration:.2f}s): {ans[:200]}...")
                
                # Validation
                missing = [k for k in test["expected_keywords"] if k not in ans]
                if missing:
                    print(f"❌ FAILED: Missing keywords {missing}")
                else:
                    print(f"✅ PASSED: All keywords found")
                    
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                print(response.text)
                
        except Exception as e:
            print(f"❌ Exception: {e}")
            
        time.sleep(2)

if __name__ == "__main__":
    run_test()
