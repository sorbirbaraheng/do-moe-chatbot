
import requests
import json
import time

BASE_URL = "http://localhost:5001"

def test_admin_sync_endpoints():
    print("🧪 Testing Admin Sync Endpoints...")
    
    # 1. Test Upload (Fake File)
    try:
        url = f"{BASE_URL}/api/admin/upload"
        files = {'file': ('test_data.csv', 'school_name,province\nSchool A,Bangkok', 'text/csv')}
        response = requests.post(url, files=files)
        
        if response.status_code == 200:
             print("✅ /api/admin/upload success:", response.json())
        else:
             print(f"❌ /api/admin/upload failed ({response.status_code}):", response.text)
    except Exception as e:
        print(f"⚠️ /api/admin/upload exception: {e}")

    # 2. Test Re-index Trigger
    try:
        url = f"{BASE_URL}/api/admin/reindex"
        data = {"target": "test_only"}
        response = requests.post(url, json=data)
        
        if response.status_code == 200:
             print("✅ /api/admin/reindex success:", response.json())
        else:
             print(f"❌ /api/admin/reindex failed ({response.status_code}):", response.text)
    except Exception as e:
        print(f"⚠️ /api/admin/reindex exception: {e}")

if __name__ == "__main__":
    # Ensure server is running or this will fail
    print("ℹ️ Ensure Flask server is running on port 5001 before running this test.")
    test_admin_sync_endpoints()
