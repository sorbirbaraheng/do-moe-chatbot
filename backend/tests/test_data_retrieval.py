#!/usr/bin/env python3
"""
🧪 Comprehensive Data Retrieval Test
Tests all major query patterns to verify fixes work correctly
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from qdrant_client import QdrantClient
from chatbot.tool_executor import ToolExecutor

def test_all():
    print("=" * 60)
    print("🧪 COMPREHENSIVE DATA RETRIEVAL TEST")
    print("=" * 60)
    
    # Initialize
    qdrant = QdrantClient(url="https://5e88ff62-cc10-4e3d-b027-da65b48ccfd5.us-west-2-0.aws.cloud.qdrant.io:6333",
                          api_key=os.getenv("QDRANT_API_KEY"))
    executor = ToolExecutor(qdrant)
    
    tests = []
    passed = 0
    failed = 0
    
    # ============================================================
    # TEST 1: School Name Normalization
    # ============================================================
    print("\n📌 TEST 1: School Name Normalization")
    
    test_names = [
        ("รร.บ้านสะบารัง", "บ้านสะบารัง"),
        ("ร.ร.บ้านมดตะนอย", "บ้านมดตะนอย"),
        ("โรงเรียนสวนกุหลาบ", "สวนกุหลาบ"),
        ("รรบ้านทุ่งนา", "บ้านทุ่งนา"),
        ("วิทยาลัยอาชีวศึกษา", "อาชีวศึกษา"),
    ]
    
    for input_name, expected in test_names:
        result, _ = executor._normalize_school_name(input_name)
        status = "✅" if result == expected else "❌"
        print(f"  {status} '{input_name}' → '{result}' (expected: '{expected}')")
        if result == expected:
            passed += 1
        else:
            failed += 1
    
    # ============================================================
    # TEST 2: Person Type Normalization
    # ============================================================
    print("\n📌 TEST 2: Person Type Normalization")
    
    test_person_types = [
        ("ครูอัตราจ้าง", "ลูกจ้างชั่วคราว"),
        ("ครู", "ข้าราชการครู"),
        ("พนักงานราชการ", "พนักงานราชการ"),  # Keep as-is
        ("ลูกจ้าง", "ลูกจ้างชั่วคราว"),
        ("ข้าราชการครู", "ข้าราชการครู"),  # Keep as-is
    ]
    
    for input_pt, expected in test_person_types:
        result = executor._normalize_person_type(input_pt)
        status = "✅" if result == expected else "❌"
        print(f"  {status} '{input_pt}' → '{result}' (expected: '{expected}')")
        if result == expected:
            passed += 1
        else:
            failed += 1
    
    # ============================================================
    # TEST 3: Province Normalization
    # ============================================================
    print("\n📌 TEST 3: Province Normalization")
    
    test_provinces = [
        ("กทม", "กรุงเทพมหานคร"),
        ("กรุงเทพฯ", "กรุงเทพมหานคร"),
        ("จ.ปัตตานี", "ปัตตานี"),
        ("จังหวัดยะลา", "ยะลา"),
        ("เชียงใหม่", "เชียงใหม่"),  # Keep as-is
    ]
    
    for input_prov, expected in test_provinces:
        result = executor._normalize_province(input_prov)
        status = "✅" if result == expected else "❌"
        print(f"  {status} '{input_prov}' → '{result}' (expected: '{expected}')")
        if result == expected:
            passed += 1
        else:
            failed += 1
    
    # ============================================================
    # TEST 4: Grade Normalization
    # ============================================================
    print("\n📌 TEST 4: Grade Normalization")
    
    test_grades = [
        ("ป.1", "ประถมศึกษาปีที่ 1"),
        ("ม.6", "มัธยมศึกษาปีที่ 6"),
        ("อนุบาล1", "อนุบาล 1"),
        ("ปวช.2", "ประกาศนียบัตรวิชาชีพปีที่ 2"),
    ]
    
    for input_grade, expected in test_grades:
        result = executor._normalize_grade(input_grade)
        status = "✅" if result == expected else "❌"
        print(f"  {status} '{input_grade}' → '{result}' (expected: '{expected}')")
        if result == expected:
            passed += 1
        else:
            failed += 1
    
    # ============================================================
    # TEST 5: Agency Normalization
    # ============================================================
    print("\n📌 TEST 5: Agency Normalization")
    
    test_agencies = [
        ("สพฐ", "สำนักงานคณะกรรมการการศึกษาขั้นพื้นฐาน"),
        ("สช", "สำนักงานคณะกรรมการส่งเสริมการศึกษาเอกชน"),
        ("อาชีวะ", "สำนักงานคณะกรรมการการอาชีวศึกษา"),
    ]
    
    for input_agency, expected in test_agencies:
        result = executor._normalize_agency(input_agency)
        status = "✅" if result == expected else "❌"
        print(f"  {status} '{input_agency}' → '{result}' (expected: '{expected}')")
        if result == expected:
            passed += 1
        else:
            failed += 1
    
    # ============================================================
    # TEST 6: Real Qdrant Query - Count Teachers by Person Type
    # ============================================================
    print("\n📌 TEST 6: Real Query - Count Teachers by Person Type")
    
    try:
        result = executor._count_teachers(province="ปัตตานี", person_type="ลูกจ้างชั่วคราว")
        total = result.get("total_teachers", 0)
        print(f"  📊 ลูกจ้างชั่วคราวในปัตตานี: {total} คน")
        if total > 0:
            print(f"  ✅ Query successful")
            passed += 1
        else:
            print(f"  ⚠️ No results found (may need data check)")
            failed += 1
    except Exception as e:
        print(f"  ❌ Error: {e}")
        failed += 1
    
    # ============================================================
    # TEST 7: Real Query - School Search with Normalized Name
    # ============================================================
    print("\n📌 TEST 7: Real Query - School Search with Prefix")
    
    try:
        result = executor._search_schools(school_name="รร.บ้านสะบารัง")
        schools = result.get("schools", [])
        print(f"  📊 Found {len(schools)} schools matching 'รร.บ้านสะบารัง'")
        if len(schools) > 0:
            print(f"  ✅ First match: {schools[0].get('school_name')}")
            passed += 1
        else:
            print(f"  ⚠️ No schools found")
            failed += 1
    except Exception as e:
        print(f"  ❌ Error: {e}")
        failed += 1
    
    # ============================================================
    # TEST 8: Real Query - Count Schools by Province
    # ============================================================
    print("\n📌 TEST 8: Real Query - Count Schools by Province")
    
    try:
        result = executor._count_schools(province="ยะลา")
        total = result.get("total_schools", 0)
        print(f"  📊 โรงเรียนในยะลา: {total} แห่ง")
        if total > 0:
            print(f"  ✅ Query successful")
            passed += 1
        else:
            print(f"  ⚠️ No results found")
            failed += 1
    except Exception as e:
        print(f"  ❌ Error: {e}")
        failed += 1
    
    # ============================================================
    # SUMMARY
    # ============================================================
    print("\n" + "=" * 60)
    print(f"📊 RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)
    
    return failed == 0

if __name__ == "__main__":
    success = test_all()
    sys.exit(0 if success else 1)
