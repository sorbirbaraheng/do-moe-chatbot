#!/usr/bin/env python3
"""
Comprehensive V5 Collection Schema Inspector
Analyzes all fields in each collection to plan filter enhancements
"""

from qdrant_client import QdrantClient
import json

client = QdrantClient(host='203.159.242.144', port=6333)

def get_all_fields(collection_name, sample_size=20):
    """Get all unique fields from a collection by sampling multiple records"""
    all_fields = {}
    
    results, _ = client.scroll(
        collection_name=collection_name,
        limit=sample_size,
        with_payload=True
    )
    
    for point in results:
        payload = point.payload
        
        # Check top-level fields
        for key, value in payload.items():
            if key == 'metadata':
                # Dive into metadata
                if isinstance(value, dict):
                    for meta_key, meta_value in value.items():
                        field_path = f"metadata.{meta_key}"
                        if field_path not in all_fields:
                            all_fields[field_path] = {
                                'type': type(meta_value).__name__,
                                'sample': str(meta_value)[:100] if meta_value else 'null',
                                'non_null_count': 0
                            }
                        if meta_value is not None and meta_value != '' and meta_value != 0:
                            all_fields[field_path]['non_null_count'] += 1
            else:
                field_path = key
                if field_path not in all_fields:
                    all_fields[field_path] = {
                        'type': type(value).__name__,
                        'sample': str(value)[:100] if value else 'null',
                        'non_null_count': 0
                    }
                if value is not None and value != '' and value != 0:
                    all_fields[field_path]['non_null_count'] += 1
    
    return all_fields, len(results)

def main():
    print("=" * 80)
    print("📊 COMPREHENSIVE V5 COLLECTION SCHEMA ANALYSIS")
    print("=" * 80)
    
    # Get all v5 collections
    response = client.get_collections()
    v5_collections = sorted([c.name for c in response.collections if c.name.endswith('v5')])
    
    print(f"\n📁 Found {len(v5_collections)} v5 collections:\n")
    
    collection_schemas = {}
    
    for col_name in v5_collections:
        print(f"\n{'=' * 80}")
        print(f"📂 COLLECTION: {col_name}")
        print("=" * 80)
        
        # Get count
        try:
            count = client.count(collection_name=col_name).count
            print(f"📊 Total Records: {count:,}")
        except Exception as e:
            print(f"⚠️ Could not get count: {e}")
            count = 0
        
        # Get fields
        fields, sample_count = get_all_fields(col_name)
        
        print(f"\n📋 Fields (from {sample_count} samples):\n")
        
        # Sort fields by path
        sorted_fields = sorted(fields.items())
        
        for field_path, info in sorted_fields:
            fill_rate = (info['non_null_count'] / sample_count * 100) if sample_count > 0 else 0
            print(f"  • {field_path}")
            print(f"    Type: {info['type']} | Fill Rate: {fill_rate:.0f}% | Sample: {info['sample'][:50]}")
        
        collection_schemas[col_name] = {
            'count': count,
            'fields': fields
        }
    
    # Summary: Fields that can be used for filtering
    print("\n" + "=" * 80)
    print("🔧 FILTER CAPABILITY MATRIX")
    print("=" * 80)
    
    filter_fields = ['school_name', 'province', 'district', 'subdistrict', 'agency', 
                     'grade', 'gender', 'year', 'school_id', 'male', 'female', 'total']
    
    print(f"\n{'Field':<20}", end="")
    for col in v5_collections:
        short_name = col.replace('edu_', '').replace('_v5', '')
        print(f"{short_name:<12}", end="")
    print()
    print("-" * (20 + 12 * len(v5_collections)))
    
    for field in filter_fields:
        print(f"{field:<20}", end="")
        for col in v5_collections:
            # Check if field exists in metadata
            has_field = any(field in fp for fp in collection_schemas[col]['fields'].keys())
            print(f"{'✅':<12}" if has_field else f"{'❌':<12}", end="")
        print()
    
    # Export as JSON for reference
    with open('v5_schemas.json', 'w', encoding='utf-8') as f:
        json.dump(collection_schemas, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Schema exported to v5_schemas.json")

if __name__ == "__main__":
    main()
