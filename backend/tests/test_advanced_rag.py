#!/usr/bin/env python3
"""
Advanced RAG Query Tester - Tests complex multi-filter queries
"""

import requests
import json
import time

API_URL = "http://127.0.0.1:5001"

# Complex queries combining multiple filters
TEST_QUERIES = [
    # 1. School + Person Type
    {
        "category": "School + PersonType",
        "query": "โรงเรียนเมืองปัตตานีมีข้าราชการครูเท่าไหร่",
        "expected_filters": ["school_name", "person_type"]
    },
    
    # 2. School + Grade
    {
        "category": "School + Grade",
        "query": "ราชประชานุเคราะห์ 40 มีนักเรียนชั้น ม.2 กี่คน",
        "expected_filters": ["school_name", "grade"]
    },
    
    # 3. Vocational School + Vocational Level + Gender
    {
        "category": "Vocational + Level + Gender",
        "query": "วิทยาลัยเทคนิคอ่างทองระดับประกาศนียบัตรวิชาชีพปีที่ 1 มีนักเรียนเพศชายกี่คน",
        "expected_filters": ["school_name", "grade (ปวช.1)", "gender"]
    },
    
    # 4. School + Kindergarten + Male Only
    {
        "category": "School + Kindergarten + Male",
        "query": "โรงเรียนสนามชัยสิทธิ์นุสรณ์ระดับชั้นอนุบาลมีนักเรียนกี่คนเพศชายอย่างเดียว",
        "expected_filters": ["school_name", "grade (อนุบาล)", "gender (ชาย)"]
    },
    
    # 5. School + Kindergarten + All Genders
    {
        "category": "School + Kindergarten + All",
        "query": "โรงเรียนสนามชัยสิทธิ์นุสรณ์ระดับชั้นอนุบาลมีนักเรียนกี่คนทั้งชายและหญิง",
        "expected_filters": ["school_name", "grade (อนุบาล)", "gender (ทั้งหมด)"]
    },
]

def test_query(query_text):
    """Send query to API and return response"""
    try:
        response = requests.post(
            f"{API_URL}/api/chat",
            json={"message": query_text},
            timeout=60  # Longer timeout for complex queries
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("response", data.get("message", str(data)))
        else:
            return f"❌ HTTP {response.status_code}: {response.text[:200]}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

def main():
    print("=" * 80)
    print("🧪 Advanced RAG Query Tester - Multi-Filter Queries")
    print("=" * 80)
    
    # Health check
    try:
        health = requests.get(f"{API_URL}/api/health", timeout=5)
        print(f"✅ API Health: {health.json()}")
    except Exception as e:
        print(f"❌ API Health Check Failed: {e}")
        return
    
    print("\n" + "=" * 80)
    
    results = []
    
    for i, test in enumerate(TEST_QUERIES, 1):
        category = test["category"]
        query = test["query"]
        expected = test["expected_filters"]
        
        print(f"\n{'='*80}")
        print(f"🔹 Test {i}/{len(TEST_QUERIES)} [{category}]")
        print(f"   Expected Filters: {expected}")
        print(f"   Q: {query}")
        print("-" * 80)
        
        start_time = time.time()
        response = test_query(query)
        elapsed = time.time() - start_time
        
        # Determine status
        if "❌" in response:
            status = "FAIL"
        elif "ไม่พบ" in response and "0" not in response:
            status = "NO DATA"
        elif len(response) < 50:
            status = "SUSPICIOUS"
        else:
            status = "PASS"
        
        print(f"   A: {response[:500]}...")
        print(f"\n   ⏱️ Time: {elapsed:.2f}s | Status: {status}")
        
        results.append({
            "category": category,
            "query": query,
            "status": status,
            "response": response,
            "time": elapsed
        })
        
        time.sleep(2)  # Rate limiting
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    no_data_count = sum(1 for r in results if r["status"] == "NO DATA")
    suspicious_count = sum(1 for r in results if r["status"] == "SUSPICIOUS")
    
    print(f"✅ PASS: {pass_count}/{len(results)}")
    print(f"❌ FAIL: {fail_count}/{len(results)}")
    print(f"⚠️ NO DATA: {no_data_count}/{len(results)}")
    print(f"🔍 SUSPICIOUS: {suspicious_count}/{len(results)}")
    
    # Detail for each
    print("\n📋 DETAILED RESULTS:")
    for i, r in enumerate(results, 1):
        status_emoji = {"PASS": "✅", "FAIL": "❌", "NO DATA": "⚠️", "SUSPICIOUS": "🔍"}.get(r["status"], "❓")
        print(f"\n{i}. [{r['category']}] {status_emoji} {r['status']}")
        print(f"   Q: {r['query'][:60]}...")
        # Show key numbers from response
        import re
        numbers = re.findall(r'\*\*(\d[,\d]*)\*\*', r['response'])
        if numbers:
            print(f"   📊 Numbers found: {numbers[:5]}")

if __name__ == "__main__":
    main()
