
import os
import sys

# Get backend dir
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(backend_dir)

from dotenv import load_dotenv
from qdrant_client import QdrantClient
import google.generativeai as genai

load_dotenv()
client = QdrantClient(url=os.getenv("QDRANT_URL", "http://203.159.242.144:6333"))

# Get API key from .env or Firestore
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    # Try getting from Firestore if not in env
    try:
        from chatbot.config_loader import ConfigLoader
        config = ConfigLoader().get_config()
        api_key = config.get("GEMINI_API_KEYS", [""])[0]
    except:
        pass

if not api_key:
    print("❌ No Gemini API Key found")
    sys.exit(1)

genai.configure(api_key=api_key)

query = "โรงเรียนอาซิสสถาน" # Try adding prefix
print(f"🔍 Semantic Search for: {query}")

embed = genai.embed_content(
    model="models/text-embedding-004",
    content=query,
    task_type="retrieval_query"
)['embedding']

res = client.query_points(
    collection_name="edu_schools_v6",
    query=embed,
    limit=5,
    score_threshold=0.0, # NO THRESHOLD
    with_payload=True
).points

for r in res:
    name = r.payload.get('metadata', {}).get('school_name')
    print(f" - {name} (Score: {r.score})")
