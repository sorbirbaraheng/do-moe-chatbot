
from qdrant_client import QdrantClient
import json

# Connect to Qdrant
client = QdrantClient(host="203.159.242.144", port=6333)

try:
    # 1. List all collections
    response = client.get_collections()
    all_collections = [c.name for c in response.collections]
    
    # 2. Filter for 'v5'
    v5_collections = [c for c in all_collections if c.endswith('v5')]
    v5_collections.sort()
    
    print(f"🔍 Found {len(v5_collections)} collections ending with 'v5':\n")
    
    for name in v5_collections:
        print(f"📂 Collection: {name}")
        
        # Get count
        count_result = client.count(collection_name=name)
        count = count_result.count
        
        # Get sample
        results = client.scroll(collection_name=name, limit=1)
        
        print(f"   📊 Total Records: {count:,}")
        
        if results[0]:
            payload = results[0][0].payload
            # Print keys only for cleaner output, or full payload if small
            print(f"   🔑 Fields: {list(payload.keys())}")
            
            # Print a snippet of 'metadata' if it exists (since we saw it earlier)
            if 'metadata' in payload:
                print(f"   📝 Metadata Keys: {list(payload['metadata'].keys())}")
                
            # Print full sample for clarity
            # print(f"   📄 Sample: {json.dumps(payload, ensure_ascii=False)[:200]}...") 
        else:
            print("   ⚠️ Empty Collection")
            
        print("-" * 60)

except Exception as e:
    print(f"❌ Error: {e}")
