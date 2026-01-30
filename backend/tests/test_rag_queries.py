#!/usr/bin/env python3
"""
RAG Query Tester - Tests diverse question types against Flask API
"""

import requests
import json
import time

API_URL = "http://127.0.0.1:5001"

# Diverse test queries based on v5 collections
TEST_QUERIES = [
    # === STATS (นับจำนวน) ===
    {"category": "Stats", "query": "ปัตตานีมีโรงเรียนกี่แห่ง"},
    {"category": "Stats", "query": "จังหวัดเชียงใหม่มีครูกี่คน"},
    {"category": "Stats", "query": "นราธิวาสมีนักเรียนกี่คน"},
    
    # === RANKING (จัดอันดับ) ===
    {"category": "Ranking", "query": "จังหวัดไหนมีโรงเรียนมากที่สุด 5 อันดับ"},
    {"category": "Ranking", "query": "อำเภอไหนในสงขลามีนักเรียนมากที่สุด"},
    
    # === COMPARISON (เปรียบเทียบ) ===
    {"category": "Comparison", "query": "เปรียบเทียบจำนวนโรงเรียนระหว่างยะลากับปัตตานี"},
    
    # === SEARCH (ค้นหา) ===
    {"category": "Search", "query": "ค้นหาโรงเรียนเตรียมอุดม"},
    {"category": "Search", "query": "โรงเรียนสวนกุหลาบอยู่ที่ไหน"},
    
    # === RATIO (อัตราส่วน) ===
    {"category": "Ratio", "query": "อัตราส่วนครูต่อนักเรียนในกรุงเทพเป็นเท่าไหร่"},
    
    # === AGENCY (สังกัด) ===
    {"category": "Agency", "query": "เชียงใหม่มีโรงเรียนสังกัด สพฐ กี่แห่ง"},
    
    # === GRADE (ระดับชั้น) ===
    {"category": "Grade", "query": "นักเรียน ม.6 ในภูเก็ตมีกี่คน"},
]

def test_query(query_text):
    """Send query to API and return response"""
    try:
        response = requests.post(
            f"{API_URL}/api/chat",
            json={"message": query_text},
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("response", data.get("message", str(data)))
        else:
            return f"❌ HTTP {response.status_code}: {response.text[:100]}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

def main():
    print("=" * 70)
    print("🧪 RAG Query Tester - Testing Diverse Question Types")
    print("=" * 70)
    
    # Health check
    try:
        health = requests.get(f"{API_URL}/api/health", timeout=5)
        print(f"✅ API Health: {health.json()}")
    except Exception as e:
        print(f"❌ API Health Check Failed: {e}")
        return
    
    print("\n" + "=" * 70)
    
    results = []
    
    for i, test in enumerate(TEST_QUERIES, 1):
        category = test["category"]
        query = test["query"]
        
        print(f"\n🔹 Test {i}/{len(TEST_QUERIES)} [{category}]")
        print(f"   Q: {query}")
        
        response = test_query(query)
        
        # Determine status
        if "❌" in response:
            status = "FAIL"
        elif "ไม่พบ" in response or "ไม่มีข้อมูล" in response:
            status = "NO DATA"
        else:
            status = "PASS"
        
        # Truncate response for display
        display_response = response[:200] + "..." if len(response) > 200 else response
        print(f"   A: {display_response}")
        print(f"   Status: {status}")
        
        results.append({
            "category": category,
            "query": query,
            "status": status,
            "response_snippet": display_response
        })
        
        time.sleep(1)  # Rate limiting
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 SUMMARY")
    print("=" * 70)
    
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    no_data_count = sum(1 for r in results if r["status"] == "NO DATA")
    
    print(f"✅ PASS: {pass_count}/{len(results)}")
    print(f"❌ FAIL: {fail_count}/{len(results)}")
    print(f"⚠️ NO DATA: {no_data_count}/{len(results)}")
    
    if fail_count > 0:
        print("\n❌ Failed Queries:")
        for r in results:
            if r["status"] == "FAIL":
                print(f"   - [{r['category']}] {r['query']}")

if __name__ == "__main__":
    main()
