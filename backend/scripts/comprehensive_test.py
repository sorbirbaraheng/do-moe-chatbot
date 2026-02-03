#!/usr/bin/env python3
"""
🧪 Comprehensive Chatbot Verification Script
Tests various scenarios to ensure the chatbot works correctly.

Usage: python backend/scripts/comprehensive_test.py
"""

import requests
import json
import time
from typing import List, Dict, Tuple

API_URL = "http://localhost:5001/api/chat"
DELAY_BETWEEN_TESTS = 2  # seconds (to avoid rate limits)

# Test cases with expected behaviors
TEST_CASES = [
    # Category 1: School Search (Should use fuzzy/semantic search)
    {
        "id": "T1",
        "name": "ค้นหาโรงเรียนพัฒนาวิทยา",
        "question": "ขอรายละเอียดโรงเรียนพัฒนาวิทยาหน่อย",
        "expect_found": True,
        "expect_keywords": ["พัฒนาวิทยา", "จังหวัด"],
        "category": "search"
    },
    {
        "id": "T2",
        "name": "ค้นหาโรงเรียน + จังหวัด",
        "question": "โรงเรียนพัฒนาวิทยา จังหวัดยะลา",
        "expect_found": True,
        "expect_keywords": ["ยะลา", "นักเรียน"],
        "category": "search"
    },
    
    # Category 2: Student Counts (Critical - Fixed bug)
    {
        "id": "T3",
        "name": "นับนักเรียนโรงเรียนเฉพาะ",
        "question": "พัฒนาวิทยา จังหวัดยะลา มีนักเรียนทั้งหมดกี่คนครับ",
        "expect_found": True,
        "expect_keywords": ["นักเรียน", "คน"],
        "category": "count_students"
    },
    {
        "id": "T4",
        "name": "นับนักเรียนระดับจังหวัด",
        "question": "จังหวัดกรุงเทพมีนักเรียนทั้งหมดกี่คน",
        "expect_found": True,
        "expect_keywords": ["กรุงเทพ", "นักเรียน"],
        "category": "count_students"
    },
    
    # Category 3: Teacher Counts
    {
        "id": "T5",
        "name": "นับครูระดับจังหวัด",
        "question": "จังหวัดเชียงใหม่มีครูกี่คน",
        "expect_found": True,
        "expect_keywords": ["เชียงใหม่", "ครู"],
        "category": "count_teachers"
    },
    
    # Category 4: School Counts
    {
        "id": "T6",
        "name": "นับโรงเรียนในจังหวัด",
        "question": "จังหวัดนครราชสีมามีโรงเรียนกี่แห่ง",
        "expect_found": True,
        "expect_keywords": ["นครราชสีมา", "โรงเรียน"],
        "category": "count_schools"
    },
    
    # Category 5: Comparison
    {
        "id": "T7",
        "name": "เปรียบเทียบจังหวัด",
        "question": "เปรียบเทียบจำนวนนักเรียนของกรุงเทพกับเชียงใหม่",
        "expect_found": True,
        "expect_keywords": ["กรุงเทพ", "เชียงใหม่", "นักเรียน"],
        "category": "compare"
    },
    
    # Category 6: Ranking
    {
        "id": "T8",
        "name": "จัดอันดับโรงเรียน",
        "question": "10 อันดับโรงเรียนที่มีนักเรียนมากที่สุดในกรุงเทพ",
        "expect_found": True,
        "expect_keywords": ["อันดับ", "โรงเรียน"],
        "category": "ranking"
    },
    
    # Category 7: Specific School Details
    {
        "id": "T9",
        "name": "รายละเอียดโรงเรียนดัง",
        "question": "ขอข้อมูลโรงเรียนสวนกุหลาบวิทยาลัย",
        "expect_found": True,
        "expect_keywords": ["สวนกุหลาบ"],
        "category": "details"
    },
    
    # Category 8: General Knowledge (Out of scope - should refuse politely)
    {
        "id": "T10",
        "name": "คำถามนอกขอบเขต",
        "question": "ผอ.โรงเรียนสวนกุหลาบชื่ออะไร",
        "expect_found": False,  # Should refuse or say data not available
        "expect_keywords": ["ไม่มี", "ไม่พบ", "ขออภัย"],
        "category": "out_of_scope"
    },
    
    # Category 9: Contextual Follow-up (Tests context memory)
    # Note: This requires simulating a conversation, simplified version here
    {
        "id": "T11",
        "name": "สัมภาษณ์ทั่วไป",
        "question": "สวัสดีครับ คุณทำอะไรได้บ้าง",
        "expect_found": True,
        "expect_keywords": ["ครับ", "ข้อมูล"],
        "category": "general_chat"
    },
    
    # Category 10: Thai Numeral Test
    {
        "id": "T12",
        "name": "เลขไทย",
        "question": "โรงเรียนบ้านหมายเลข ๑ มีกี่คน",  # Edge case
        "expect_found": False,  # May or may not find, but shouldn't crash
        "expect_keywords": [],
        "category": "edge_case"
    }
]


def send_question(question: str) -> Tuple[bool, str, Dict]:
    """Send a question to the chatbot API and return (success, response_text, full_json)"""
    try:
        payload = {"message": question}
        response = requests.post(API_URL, json=payload, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            response_text = data.get("response", "")
            return True, response_text, data
        else:
            return False, f"HTTP {response.status_code}: {response.text}", {}
            
    except requests.exceptions.Timeout:
        return False, "TIMEOUT", {}
    except Exception as e:
        return False, f"ERROR: {str(e)}", {}


def evaluate_response(test_case: Dict, response_text: str) -> Dict:
    """Evaluate if the response meets expectations"""
    result = {
        "id": test_case["id"],
        "name": test_case["name"],
        "category": test_case["category"],
        "question": test_case["question"],
        "response_preview": response_text[:200] + "..." if len(response_text) > 200 else response_text,
        "passed": True,
        "issues": []
    }
    
    # Check for error responses
    if "ไม่พบข้อมูล" in response_text or "not found" in response_text.lower():
        if test_case["expect_found"]:
            result["passed"] = False
            result["issues"].append("❌ Expected to find data but got 'Not Found'")
    
    # Check for expected keywords
    missing_keywords = []
    for kw in test_case.get("expect_keywords", []):
        if kw not in response_text:
            missing_keywords.append(kw)
    
    if missing_keywords and test_case["expect_found"]:
        result["issues"].append(f"⚠️ Missing keywords: {', '.join(missing_keywords)}")
        # Don't fail hard on missing keywords, just warn
    
    # Check for crashes or raw JSON
    if response_text.startswith("{") or response_text.startswith("["):
        result["passed"] = False
        result["issues"].append("❌ Got raw JSON instead of natural language")
    
    # Check for rate limit errors
    if "rate limit" in response_text.lower() or "quota" in response_text.lower():
        result["passed"] = False
        result["issues"].append("⚠️ Rate limit hit")
    
    return result


def run_all_tests():
    """Run all test cases and print a summary"""
    print("=" * 60)
    print("🧪 COMPREHENSIVE CHATBOT VERIFICATION")
    print("=" * 60)
    print(f"📋 Total Tests: {len(TEST_CASES)}")
    print(f"🌐 API: {API_URL}")
    print("=" * 60)
    
    results = []
    passed_count = 0
    failed_count = 0
    
    for i, test in enumerate(TEST_CASES, 1):
        print(f"\n[{i}/{len(TEST_CASES)}] Testing: {test['name']}...")
        print(f"   Question: {test['question']}")
        
        success, response_text, full_data = send_question(test["question"])
        
        if not success:
            result = {
                "id": test["id"],
                "name": test["name"],
                "category": test["category"],
                "question": test["question"],
                "response_preview": response_text,
                "passed": False,
                "issues": [f"❌ API Error: {response_text}"]
            }
        else:
            result = evaluate_response(test, response_text)
        
        results.append(result)
        
        if result["passed"]:
            passed_count += 1
            print(f"   ✅ PASSED")
        else:
            failed_count += 1
            print(f"   ❌ FAILED: {', '.join(result['issues'])}")
        
        # Brief response preview
        if response_text:
            preview = response_text[:100].replace("\n", " ")
            print(f"   📝 Response: {preview}...")
        
        # Delay to avoid rate limits
        if i < len(TEST_CASES):
            time.sleep(DELAY_BETWEEN_TESTS)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    print(f"✅ Passed: {passed_count}/{len(TEST_CASES)}")
    print(f"❌ Failed: {failed_count}/{len(TEST_CASES)}")
    
    # Detailed failures
    if failed_count > 0:
        print("\n🔍 FAILED TESTS DETAILS:")
        for r in results:
            if not r["passed"]:
                print(f"\n   [{r['id']}] {r['name']}")
                print(f"      Category: {r['category']}")
                print(f"      Question: {r['question']}")
                for issue in r["issues"]:
                    print(f"      {issue}")
    
    # Category breakdown
    print("\n📈 BY CATEGORY:")
    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"passed": 0, "failed": 0}
        if r["passed"]:
            categories[cat]["passed"] += 1
        else:
            categories[cat]["failed"] += 1
    
    for cat, stats in categories.items():
        total = stats["passed"] + stats["failed"]
        print(f"   {cat}: {stats['passed']}/{total}")
    
    print("\n" + "=" * 60)
    
    return results


if __name__ == "__main__":
    run_all_tests()
