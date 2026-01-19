#!/usr/bin/env python3
"""
🏫 DO-MOE School Category - Comprehensive API Test Suite
ทดสอบคำถามหมวดหมู่โรงเรียนตั้งแต่ง่ายไปจนถึงซับซ้อน

รันด้วย: python test_school_comprehensive.py
"""

import requests
import json
import time
import sys
from typing import Dict, List, Tuple

# Configuration
BASE_URL = "http://localhost:5001/api/chat"
HEADERS = {"Content-Type": "application/json"}
TIMEOUT = 30  # seconds

# Color codes for terminal
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

# =========================================================================
# TEST CASES - School Category
# =========================================================================
TEST_CASES = [
    # ===================== LEVEL 1: SIMPLE (ง่าย) =====================
    {
        "category": "🟢 SIMPLE",
        "tests": [
            # Basic greeting
            {"q": "สวัสดี", "desc": "Greeting", "expect_type": "greeting"},
            # Simple school count
            {"q": "ปัตตานีมีโรงเรียนกี่แห่ง", "desc": "Province count", "expect_type": "count"},
            {"q": "จังหวัดยะลามีโรงเรียนกี่โรง", "desc": "Another province count", "expect_type": "count"},
            # General info
            {"q": "โรงเรียนคืออะไร", "desc": "General question", "expect_type": "general"},
            {"q": "กระทรวงศึกษาธิการทำอะไร", "desc": "Ministry info", "expect_type": "general"},
        ]
    },
    
    # ===================== LEVEL 2: INTERMEDIATE (ปานกลาง) =====================
    {
        "category": "🟡 INTERMEDIATE",
        "tests": [
            # District-level count
            {"q": "อำเภอเมืองปัตตานีมีโรงเรียนกี่แห่ง", "desc": "District count", "expect_type": "count"},
            {"q": "อำเภอเมืองยะลามีโรงเรียนเท่าไหร่", "desc": "District count 2", "expect_type": "count"},
            # List schools
            {"q": "รายชื่อโรงเรียนในจังหวัดนราธิวาส", "desc": "Province list", "expect_type": "list"},
            {"q": "แสดงโรงเรียนในอำเภอหาดใหญ่", "desc": "District list", "expect_type": "list"},
            # Specific school info
            {"q": "ขอข้อมูลโรงเรียนบำรุงอิสลาม", "desc": "School detail", "expect_type": "detail"},
            {"q": "โรงเรียนสตรียะลาอยู่ตรงไหน", "desc": "School location", "expect_type": "detail"},
            # Agency filter
            {"q": "สพฐ. มีโรงเรียนกี่แห่ง", "desc": "Agency count", "expect_type": "count"},
        ]
    },
    
    # ===================== LEVEL 3: ADVANCED (ซับซ้อน) =====================
    {
        "category": "🟠 ADVANCED",
        "tests": [
            # Multi-level filter (Province + District + Subdistrict)
            {"q": "ตำบลบานาอำเภอเมืองปัตตานีมีโรงเรียนอะไรบ้าง", "desc": "Subdistrict filter", "expect_type": "list"},
            {"q": "โรงเรียนในตำบลสะเตง อำเภอเมืองยะลา", "desc": "Multi-level 2", "expect_type": "list"},
            # Ranking - Most
            {"q": "ภาคใต้จังหวัดไหนมีโรงเรียนมากที่สุด", "desc": "Regional ranking (most)", "expect_type": "ranking"},
            {"q": "จังหวัดไหนมีโรงเรียนเยอะที่สุดในภาคเหนือ", "desc": "North ranking", "expect_type": "ranking"},
            {"q": "อำเภอไหนในยะลามีโรงเรียนมากที่สุด", "desc": "District ranking", "expect_type": "ranking"},
            # Ranking - Least  
            {"q": "ยะลาอำเภอไหนมีโรงเรียนน้อยที่สุด", "desc": "District least", "expect_type": "ranking"},
            {"q": "ตำบลไหนในอำเภอเมืองปัตตานีมีโรงเรียนน้อยสุด", "desc": "Subdistrict least", "expect_type": "ranking"},
        ]
    },
    
    # ===================== LEVEL 4: COMPLEX (ยากมาก) =====================
    {
        "category": "🔴 COMPLEX",
        "tests": [
            # Comparison
            {"q": "เปรียบเทียบจำนวนโรงเรียนระหว่างยะลากับปัตตานี", "desc": "Province comparison", "expect_type": "comparison"},
            {"q": "กรุงเทพกับเชียงใหม่มีโรงเรียนต่างกันเท่าไหร่", "desc": "BKK vs CM", "expect_type": "comparison"},
            # Complex aggregate
            {"q": "10 จังหวัดที่มีโรงเรียนมากที่สุดในประเทศ", "desc": "Top 10 provinces", "expect_type": "ranking"},
            {"q": "รายชื่ออำเภอในสงขลาเรียงตามจำนวนโรงเรียน", "desc": "Sorted list", "expect_type": "ranking"},
            # Multi-step reasoning
            {"q": "สช.มีโรงเรียนในภาคใต้กี่แห่ง", "desc": "Agency + Region", "expect_type": "count"},
            {"q": "อำเภอเมืองของแต่ละจังหวัดในภาคใต้มีโรงเรียนเฉลี่ยกี่แห่ง", "desc": "Average calc", "expect_type": "analysis"},
        ]
    },
    
    # ===================== EDGE CASES =====================
    {
        "category": "⚪ EDGE CASES",
        "tests": [
            # Keyword only
            {"q": "โรงเรียน", "desc": "Single keyword", "expect_type": "general"},
            # Typos / Variations
            {"q": "ปตานี มีโรงเรียนกี่แห่ง", "desc": "Typo handling", "expect_type": "count"},
            {"q": "กทม มีโรงเรียนเท่าไหร่", "desc": "Abbreviation", "expect_type": "count"},
            # Follow-up context (simulate conversation)
            {"q": "แล้วอำเภอไหนมีมากที่สุด", "desc": "Follow-up (no context)", "expect_type": "followup"},
            # Empty / vague
            {"q": "ช่วยหาโรงเรียนหน่อย", "desc": "Vague request", "expect_type": "clarification"},
        ]
    },
]


def test_api(question: str, desc: str) -> Tuple[bool, str, float]:
    """
    Send question to API and return (success, response_summary, response_time)
    """
    payload = {
        "message": question,
        "category": "school",
        "session_id": f"test-comprehensive-{int(time.time())}"
    }
    
    start = time.time()
    try:
        response = requests.post(BASE_URL, json=payload, headers=HEADERS, timeout=TIMEOUT)
        elapsed = time.time() - start
        
        if response.status_code == 200:
            data = response.json()
            answer = data.get("response", "") or data.get("message", "")
            
            # Check if response is meaningful (not empty or error)
            if answer and len(answer) > 10:
                # Truncate for display
                summary = (answer[:80] + '..') if len(answer) > 80 else answer
                return True, summary.replace('\n', ' '), elapsed
            else:
                return False, "Empty or too short response", elapsed
        else:
            return False, f"HTTP {response.status_code}", elapsed
            
    except requests.Timeout:
        return False, "Request timeout", TIMEOUT
    except requests.ConnectionError:
        return False, "Connection failed - is server running?", 0
    except Exception as e:
        return False, str(e)[:50], 0


def run_all_tests():
    """Run all test cases and print results"""
    print(f"\n{BOLD}{'='*90}{RESET}")
    print(f"{BOLD}{CYAN}🏫 DO-MOE School Category - Comprehensive API Test Suite{RESET}")
    print(f"{BOLD}{'='*90}{RESET}")
    print(f"Target: {BASE_URL}")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*90}\n")
    
    total_tests = 0
    passed_tests = 0
    failed_tests = []
    total_time = 0
    
    for category in TEST_CASES:
        cat_name = category["category"]
        tests = category["tests"]
        
        print(f"\n{BOLD}{cat_name}{RESET}")
        print("-" * 80)
        
        for test in tests:
            total_tests += 1
            q = test["q"]
            desc = test["desc"]
            
            success, summary, elapsed = test_api(q, desc)
            total_time += elapsed
            
            if success:
                passed_tests += 1
                status = f"{GREEN}✓ PASS{RESET}"
            else:
                failed_tests.append({"category": cat_name, "desc": desc, "question": q, "error": summary})
                status = f"{RED}✗ FAIL{RESET}"
            
            # Print result line
            print(f"  {status} [{elapsed:.2f}s] {desc:<25} | {summary[:50]}")
    
    # Summary
    print(f"\n{BOLD}{'='*90}{RESET}")
    print(f"{BOLD}📊 SUMMARY{RESET}")
    print(f"{'='*90}")
    
    pass_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
    
    if pass_rate == 100:
        color = GREEN
    elif pass_rate >= 80:
        color = YELLOW
    else:
        color = RED
    
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {GREEN}{passed_tests}{RESET}")
    print(f"Failed: {RED}{len(failed_tests)}{RESET}")
    print(f"Pass Rate: {color}{pass_rate:.1f}%{RESET}")
    print(f"Total Time: {total_time:.2f}s")
    print(f"Avg Response Time: {(total_time/total_tests):.2f}s" if total_tests > 0 else "N/A")
    
    # Failed tests detail
    if failed_tests:
        print(f"\n{BOLD}{RED}❌ Failed Tests:{RESET}")
        for ft in failed_tests:
            print(f"  - [{ft['category']}] {ft['desc']}: {ft['question']}")
            print(f"    Error: {ft['error']}")
    
    print(f"\n{'='*90}\n")
    
    return passed_tests == total_tests


def check_server():
    """Check if server is running"""
    try:
        response = requests.get("http://localhost:5001/api/health", timeout=5)
        if response.status_code == 200:
            print(f"{GREEN}✓ Server is running{RESET}")
            return True
    except:
        pass
    
    print(f"{RED}✗ Server is not running!{RESET}")
    print(f"Please start the Flask server first:")
    print(f"  cd backend && python web_chatbot_v5.py --api --port 5001")
    return False


if __name__ == "__main__":
    print(f"\n{BOLD}Checking server status...{RESET}")
    
    if not check_server():
        sys.exit(1)
    
    all_passed = run_all_tests()
    sys.exit(0 if all_passed else 1)
