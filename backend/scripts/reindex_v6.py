
import os
import time
import sys
import logging
from typing import List, Dict

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from google import genai
from chatbot.llm import MultiProviderLLM
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from tqdm import tqdm

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Config
OLD_COLLECTION = "edu_schools_v5"
NEW_COLLECTION = "edu_schools_v6"
EMBEDDING_MODEL = "models/text-embedding-004"
BATCH_SIZE = 50
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not all([QDRANT_URL, GEMINI_API_KEY]):
    logger.error("❌ Missing Required API Keys (QDRANT_URL or GEMINI_API_KEY) in .env")
    sys.exit(1)

# Initialize Clients
try:
    llm = MultiProviderLLM()
    qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
except Exception as e:
    logger.error(f"❌ Client init failed: {e}")
    sys.exit(1)

def setup_collection():
    """Create new collection if not exists"""
    exists = qdrant.collection_exists(NEW_COLLECTION)
    if not exists:
        logger.info(f"Creating collection {NEW_COLLECTION}...")
        qdrant.create_collection(
            collection_name=NEW_COLLECTION,
            vectors_config=VectorParams(size=768, distance=Distance.COSINE)
        )
        logger.info("✅ Collection created")
    else:
        logger.info(f"ℹ️ Collection {NEW_COLLECTION} already exists")

def generate_rich_text(payload: Dict) -> str:
    """Create rich text representation for semantic search"""
    name = payload.get("school_name", "")
    province = payload.get("province", "")
    district = payload.get("district", "")
    subdistrict = payload.get("subdistrict", "")
    agency = payload.get("agency", "")
    students = payload.get("total_students", 0)
    
    # Enhanced Context String
    text = f"โรงเรียน {name} ตั้งอยู่ที่ตำบล{subdistrict} อำเภอ{district} จังหวัด{province} สังกัด {agency} มีนักเรียนประมาณ {students} คน"
    
    # Add keywords for better matching
    if "วิทยาลัย" in name:
        text += " (ระดับอาชีวศึกษา/ปวช/ปวส)"
    elif "อนุบาล" in name:
        text += " (ระดับปฐมวัย/อนุบาล)"
        
    return text

def reindex_data():
    setup_collection()
    
    logger.info(f"📥 Fetching data from {OLD_COLLECTION}...")
    
    # Scroll all data from old collection
    offset = None
    all_points = []
    
    while True:
        points, next_offset = qdrant.scroll(
            collection_name=OLD_COLLECTION,
            limit=1000,
            offset=offset,
            with_payload=True,
            with_vectors=False
        )
        all_points.extend(points)
        offset = next_offset
        if offset is None:
            break
            
    total = len(all_points)
    logger.info(f"📊 Total schools to re-index: {total}")
    
    # Process in batches
    for i in tqdm(range(0, total, BATCH_SIZE)):
        batch = all_points[i:i + BATCH_SIZE]
        points_to_upload = []
        texts_to_embed = []
        metadatas = []
        ids = []
        
        # Prepare Batch
        for point in batch:
            payload = point.payload.get("metadata", point.payload) # Handle nested metadata if present
            
            # Normalize payload structure (flatten if needed)
            if "metadata" in payload:
                payload = payload["metadata"]
                
            rich_text = generate_rich_text(payload)
            payload["text"] = rich_text # Update text field for hybrid search
            
            texts_to_embed.append(rich_text)
            metadatas.append(payload)
            ids.append(point.id)
            
        # Generate Embeddings
        try:
            # Gemini Batch Embedding
            vectors = []
            for text in texts_to_embed:
                # LLM helper handles rotation
                try:
                    v = llm.embed_content(text)
                    vectors.append(v)
                except Exception as e:
                    logger.warning(f"Skipping failed embedding: {e}")
                    vectors.append([0.0]*768) # Fallback zero vector
            
            # Create Points
            for j, vector in enumerate(vectors):
                points_to_upload.append(PointStruct(
                    id=ids[j],
                    vector=vector,
                    payload={"metadata": metadatas[j], "text": texts_to_embed[j]}
                ))
                
            # Upload
            qdrant.upsert(
                collection_name=NEW_COLLECTION,
                points=points_to_upload
            )
            
            # Rate limit handling (Gemini is generous but safe side)
            time.sleep(1) 
            
        except Exception as e:
            logger.error(f"❌ Batch execution failed: {e}")
            # Continue to next batch instead of stopping
            continue
            
    logger.info("🎉 Re-indexing Completed Successfully!")

if __name__ == "__main__":
    reindex_data()
