
import requests
import time
import json
import threading

# Config
BASE_URL = "http://localhost:5001/api/chat/stream"
LIMIT = 60
TEST_COUNT = 70  # Should trigger limit

def send_request(i):
    try:
        start = time.time()
        payload = {
            "message": "test spam",
            "history": [],
            "session_id": f"test_spam_{i}"
        }
        resp = requests.post(BASE_URL, json=payload, timeout=5)
        duration = time.time() - start
        
        if resp.status_code == 429:
            print(f"[{i}] ⛔️ BLOCKED (429) - {resp.json().get('error')}")
            return True
        elif resp.status_code == 200:
            print(f"[{i}] ✅ OK ({duration:.2f}s)")
            return False
        else:
            print(f"[{i}] ⚠️ STATUS {resp.status_code}")
            return False
            
    except Exception as e:
        print(f"[{i}] ❌ ERROR: {e}")
        return False

print(f"🚀 Starting spam test: {TEST_COUNT} requests (Limit is ~{LIMIT}/min)...")

blocked_count = 0
for i in range(TEST_COUNT):
    is_blocked = send_request(i)
    if is_blocked:
        blocked_count += 1
    # Very fast, barely any sleep to simulate spam
    time.sleep(0.05) 

print(f"\n📊 Result: Blocked {blocked_count} requests.")
if blocked_count > 0:
    print("✅ Rate limiting IS WORKING.")
else:
    print("❌ Rate limiting FAILED (No blocks).")
