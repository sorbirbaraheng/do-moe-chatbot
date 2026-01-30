
import os
import json
from qdrant_client import QdrantClient

# Configuration
QDRANT_URL = "http://203.159.242.144:6333"

def inspect_all_v5_collections():
    print(f"🔌 Connecting to Qdrant at {QDRANT_URL}...")
    try:
        client = QdrantClient(url=QDRANT_URL, timeout=10)
        
        # 1. Get all collections
        collections_response = client.get_collections()
        all_collections = [c.name for c in collections_response.collections]
        
        # 2. Filter for 'v5' collections
        v5_collections = [c for c in all_collections if c.endswith('v5')]
        
        print(f"✅ Found {len(v5_collections)} 'v5' collections: {v5_collections}\n")
        
        for collection_name in v5_collections:
            print(f"📦 INSPECTING: {collection_name}")
            print("=" * 60)
            
            # Get one point to inspect its full structure
            results = client.scroll(
                collection_name=collection_name,
                limit=1,
                with_payload=True,
                with_vectors=False
            )
            
            if results[0]:
                point = results[0][0]
                metadata = point.payload.get('metadata', {})
                
                # Print keys and sample values
                for key, value in sorted(metadata.items()): # Sort keys for readability
                    val_str = str(value)
                    if len(val_str) > 100:
                        val_str = val_str[:100] + "..."
                    print(f"🔹 {key}: {val_str} (Type: {type(value).__name__})")
                    
                print("-" * 60)
            else:
                print(f"❌ Collection '{collection_name}' is empty.")
            print("\n")

    except Exception as e:
        print(f"❌ Error inspecting collections: {e}")

if __name__ == "__main__":
    inspect_all_v5_collections()
