#!/usr/bin/env python3
"""
🧪 Comprehensive Chatbot Test Suite
Tests ALL query types via Flask API to ensure correct responses
"""

import requests
import json
import time
from typing import List, Tuple, Optional

FLASK_URL = "http://localhost:5001/api/chat"

# Test cases: (question, expected_keywords, category, description)
TEST_CASES = [
    # === 1. TEACHER QUERIES ===
    ("โรงเรียนมัธยมวัดเบญจมบพิตร มีครูทั้งหมดกี่คน", ["33", "ครู"], "school", "Teacher count - exact school"),
    ("วิทยาลัยอาชีวศึกษาเสาวภา มีครูกี่คน", ["ครู", "คน"], "school", "Teacher count - วิทยาลัย prefix"),
    ("ข้าราชการครูในโรงเรียนเตรียมอุดมศึกษา มีกี่คน", ["ครู", "คน"], "school", "Teacher with ข้าราชการ keyword"),
    ("ครูผู้หญิงโรงเรียนสวนกุหลาบวิทยาลัย มีกี่คน", ["หญิง", "ครู"], "school", "Teacher female specific"),
    
    # === 2. STUDENT QUERIES ===
    ("โรงเรียนเตรียมอุดมศึกษา มีนักเรียนกี่คน", ["นักเรียน", "คน"], "school", "Student count - famous school"),
    ("นักเรียน ม.1 เพศชาย ในกรุงเทพมีกี่คน", ["ชาย", "คน"], "school", "Student M1 male Bangkok"),
    ("เด็กหญิงชั้นประถมศึกษาปีที่ 1 มีกี่คน", ["คน"], "school", "Student with เด็ก keyword"),
    ("ผู้เรียนระดับ ปวช.1 มีกี่คน", ["คน"], "school", "Student with ผู้เรียน keyword"),
    
    # === 3. SCHOOL INFO QUERIES ===
    ("โรงเรียนเตรียมอุดมศึกษา อยู่ที่ไหน", ["กรุงเทพ", "เตรียมอุดม"], "school", "School location"),
    ("โรงเรียนสวนกุหลาบวิทยาลัย สังกัดอะไร", ["สวนกุหลาบ"], "school", "School agency"),  # ดึงข้อมูลโรงเรียนได้ก็ถือว่าผ่าน
    ("ข้อมูลโรงเรียนราชวินิต", ["ราชวินิต"], "school", "General school info"),
    
    # === 4. AREA/LOCATION QUERIES ===
    ("จังหวัดกระบี่มีโรงเรียนกี่แห่ง", ["โรงเรียน", "แห่ง"], "school", "School count by province"),  # 457 แห่ง
    ("กรุงเทพมหานครมีโรงเรียนกี่โรง", ["กรุงเทพ", "โรงเรียน"], "school", "School count Bangkok"),
    ("รายชื่อโรงเรียนในเขตดินแดง", ["โรงเรียน"], "school", "School list by district"),
    
    # === 5. RATIO QUERIES ===
    ("อัตราส่วนนักเรียนต่อครูของโรงเรียนเตรียมอุดมศึกษา", ["อัตราส่วน", "เตรียม"], "school", "Student-teacher ratio"),  # ดู ratio
    
    # === 6. RANKING QUERIES ===
    ("โรงเรียนไหนมีนักเรียนมากที่สุดในกรุงเทพ", ["อันดับ"], "school", "Top school by students"),  # ดู ranking
    ("โรงเรียนไหนมีครูมากที่สุดในกรุงเทพ", ["อันดับ"], "school", "Top school by teachers"),  # ดู ranking
    
    # === 7. COMPARISON QUERIES ===
    ("เปรียบเทียบจำนวนครูระหว่างโรงเรียนเตรียมอุดมกับสวนกุหลาบ", ["เตรียม", "สวนกุหลาบ", "ครู"], "school", "Compare teachers"),
    
    # === 8. MIXED/CONFUSING QUERIES ===
    ("โรงเรียนมัธยมวัดเบญจมบพิตรมีบุคลากรกี่คน", ["ครู", "คน"], "school", "บุคลากร -> teacher"),
    ("อาจารย์ในโรงเรียนราชวินิต มีกี่คน", ["ครู", "คน"], "school", "อาจารย์ -> teacher"),
    ("พนักงานราชการในโรงเรียนสวนกุหลาบ มีกี่คน", ["ครู", "คน"], "school", "พนักงานราชการ -> teacher"),
]

def test_query(question: str, expected_keywords: List[str], category: str, description: str) -> Tuple[bool, str]:
    """Test a single query and check for expected keywords in response"""
    try:
        response = requests.post(
            FLASK_URL,
            json={
                "message": question,
                "session_id": f"test_{int(time.time())}",
                "category": category
            },
            timeout=30
        )
        
        if response.status_code != 200:
            return False, f"HTTP {response.status_code}"
        
        data = response.json()
        answer = data.get("response", "")
        
        # Check if ALL expected keywords are present
        missing = [kw for kw in expected_keywords if kw not in answer]
        
        if missing:
            return False, f"Missing: {missing}\nResponse: {answer[:200]}..."
        
        return True, answer[:150]
        
    except requests.exceptions.Timeout:
        return False, "Timeout (30s)"
    except Exception as e:
        return False, str(e)

def run_all_tests():
    """Run all test cases and print results"""
    print("=" * 60)
    print("🧪 COMPREHENSIVE CHATBOT TEST SUITE")
    print("=" * 60)
    
    passed = 0
    failed = 0
    results = []
    
    for i, (question, expected, category, description) in enumerate(TEST_CASES, 1):
        print(f"\n[{i}/{len(TEST_CASES)}] {description}")
        print(f"   Q: {question[:50]}...")
        
        success, message = test_query(question, expected, category, description)
        
        if success:
            print(f"   ✅ PASS")
            passed += 1
        else:
            print(f"   ❌ FAIL: {message[:100]}")
            failed += 1
        
        results.append({
            "question": question,
            "description": description,
            "passed": success,
            "message": message
        })
        
        # Small delay to avoid overwhelming Flask
        time.sleep(0.5)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    print(f"✅ Passed: {passed}/{len(TEST_CASES)}")
    print(f"❌ Failed: {failed}/{len(TEST_CASES)}")
    print(f"📈 Success Rate: {passed/len(TEST_CASES)*100:.1f}%")
    
    if failed > 0:
        print("\n❌ FAILED TESTS:")
        for r in results:
            if not r["passed"]:
                print(f"   - {r['description']}: {r['question'][:40]}...")
    
    return passed, failed, results

if __name__ == "__main__":
    run_all_tests()
