
from qdrant_client import QdrantClient
import json
import os

# Connect to Qdrant
# Using the IP found in web_chatbot_v5.py default
client = QdrantClient(host="203.159.242.144", port=6333)

def serialize_payload(payload):
    """Serialize payload to JSON, handling non-serializable objects if any"""
    try:
        return json.dumps(payload, ensure_ascii=False, indent=2)
    except TypeError:
        return str(payload)

try:
    print("🔌 Connecting to Qdrant...")
    # 1. List all collections
    response = client.get_collections()
    all_collections = [c.name for c in response.collections]
    
    # 2. Filter for 'v5'
    v5_collections = [c for c in all_collections if c.endswith('v5')]
    v5_collections.sort()
    
    print(f"🔍 Found {len(v5_collections)} collections ending with 'v5':\n")
    
    for name in v5_collections:
        print(f"📂 COLLECTION: {name}")
        print("=" * 60)
        
        # Get count
        try:
            count_result = client.count(collection_name=name)
            count = count_result.count
            print(f"📊 Total Records: {count:,}")
        except Exception as e:
            print(f"⚠️ Could not get count: {e}")

        # Get sample
        try:
            results = client.scroll(collection_name=name, limit=1)
            
            if results[0]:
                point = results[0][0]
                payload = point.payload
                
                print(f"🆔 Sample ID: {point.id}")
                print("📄 RAW PAYLOAD DATA:")
                print("-" * 20)
                print(serialize_payload(payload))
                print("-" * 20)
                
                # If there is 'metadata' key, highlight it as it's often the main content
                if 'metadata' in payload:
                    print("📝 METADATA FIELDS (Summary):")
                    for k, v in payload['metadata'].items():
                         print(f"   - {k}: {type(v).__name__}")
            else:
                print("⚠️ Collection is empty (no records found)")
                
        except Exception as e:
            print(f"❌ Error fetching sample: {e}")
            
        print("\n" + "=" * 60 + "\n")

except Exception as e:
    print(f"❌ Fatal Error: {e}")
