
import requests
import json
import time

BASE_URL = "http://localhost:5001/api/chat"
headers = {"Content-Type": "application/json"}

test_cases = [
    # Basic - Count
    {"q": "จังหวัดกรุงเทพมีโรงเรียนกี่แห่ง", "desc": "Basic Count"},
    # Basic - List
    {"q": "รายชื่อโรงเรียนในจังหวัดปัตตานี", "desc": "Basic List"},
    # Intermediate - Filtered Count
    {"q": "อำเภอเมืองปัตตานีมีโรงเรียนกี่แห่ง", "desc": "District Count"},
    # Intermediate - Detail
    {"q": "ขอข้อมูลโรงเรียนบำรุงอิสลาม", "desc": "School Detail"},
    # Advanced - Ranking
    {"q": "จังหวัดไหนในภาคใต้มีโรงเรียนมากที่สุด", "desc": "Regional Ranking"},
    # Complex - Comparison
    {"q": "เปรียบเทียบจำนวนโรงเรียนระหว่างยะลากับปัตตานี", "desc": "Comparison"},
    # Edge Case
    {"q": "โรงเรียน", "desc": "Keyword Only"}
]

print(f"{'TEST NAME':<20} | {'STATUS':<10} | {'RESPONSE SUMMARY'}")
print("-" * 80)

for test in test_cases:
    payload = {
        "message": test["q"],
        "category": "school",
        "session_id": "test-auto-001"
    }
    try:
        response = requests.post(BASE_URL, json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            answer = data.get("response", "") or data.get("message", "")
            # Truncate answer for display
            summary = (answer[:60] + '..') if len(answer) > 60 else answer
            print(f"{test['desc']:<20} | PASS       | {summary.replace(chr(10), ' ')}")
        else:
            print(f"{test['desc']:<20} | FAIL {response.status_code} | -")
    except Exception as e:
        print(f"{test['desc']:<20} | ERROR      | {str(e)}")
