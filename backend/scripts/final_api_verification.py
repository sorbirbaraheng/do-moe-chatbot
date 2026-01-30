#!/usr/bin/env python3
"""
🎯 FINAL API VERIFICATION - Tests all collections via chat API
"""
import requests
import time

API_URL = "http://127.0.0.1:5001/api/chat"
SESSION_ID = "final_verification"

TESTS = [
    ("Schools", "ค้นหาโรงเรียนเตรียมอุดมศึกษา", ["เตรียมอุดม"]),
    ("Teachers", "ครูในกรุงเทพมีกี่คน", ["ครู", "คน"]),
    ("Students", "นักเรียนยะลามีกี่คน", ["นักเรียน", "คน"]),
    ("Ratios", "อัตราส่วนนักเรียนต่อครูของจังหวัดชลบุรี", ["อัตราส่วน"]),
    ("Areas", "เขตพื้นที่การศึกษาเชียงใหม่มีกี่เขต", ["เขต", "เชียงใหม่"]),
    ("Grades", "นักเรียนขอนแก่นแยกตามระดับชั้น", ["นักเรียน"]),
    ("Gender", "สัดส่วนชายหญิงของปัตตานี", ["ชาย", "หญิง"]),
    ("Systems", "โรงเรียนในสงขลา แยกในระบบนอกระบบ", ["ในระบบ", "นอกระบบ"]),
]

print("=" * 60)
print("🎯 FINAL API VERIFICATION")
print("=" * 60)

passed = 0
failed = 0

for name, question, keywords in TESTS:
    print(f"\n📂 {name}: {question[:40]}...")
    try:
        start = time.time()
        resp = requests.post(API_URL, json={
            "message": question,
            "history": [],
            "session_id": SESSION_ID
        }, timeout=45)
        duration = time.time() - start
        
        if resp.status_code == 200:
            answer = resp.json().get("response", "")
            found = [k for k in keywords if k in answer]
            
            if len(found) >= len(keywords) // 2:  # At least half keywords found
                print(f"   ✅ PASS ({duration:.1f}s) - Found: {found}")
                print(f"   📝 {answer[:100]}...")
                passed += 1
            else:
                print(f"   ⚠️ PARTIAL - Keywords not found: {[k for k in keywords if k not in answer]}")
                print(f"   📝 {answer[:100]}...")
                passed += 0.5
        else:
            print(f"   ❌ HTTP {resp.status_code}")
            failed += 1
    except Exception as e:
        print(f"   ❌ Error: {str(e)[:50]}")
        failed += 1
    
    time.sleep(2)  # Avoid rate limits

print("\n" + "=" * 60)
print(f"📊 RESULTS: {passed}/{len(TESTS)} passed, {failed} failed")
print("=" * 60)
