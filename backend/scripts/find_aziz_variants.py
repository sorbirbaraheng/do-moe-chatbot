
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchText
import logging

logging.basicConfig(level=logging.WARNING)
load_dotenv()

qdrant_url = os.getenv("QDRANT_URL", "http://203.159.242.144:6333")
client = QdrantClient(url=qdrant_url, timeout=10)

print("🔍 Searching for 'อาซิส' or 'อาซิซ' in school names...")

keywords = ["อาซิส", "อาซิซ", "อาซีซ", "aziz"]

for kw in keywords:
    print(f"\n📋 Keyword: {kw}")
    try:
        results = client.scroll(
            collection_name="edu_schools_v6",
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="school_name",
                        match=MatchText(text=kw)
                    )
                ]
            ),
            limit=10,
            with_payload=True
        )[0]
        
        if results:
            for r in results:
                name = r.payload.get('metadata', {}).get('school_name', 'N/A')
                prov = r.payload.get('metadata', {}).get('province', 'N/A')
                print(f"   - {name} (จ.{prov})")
        else:
            print("   ❌ Not found")
    except Exception as e:
        print(f"   ⚠️ Error: {e}")
