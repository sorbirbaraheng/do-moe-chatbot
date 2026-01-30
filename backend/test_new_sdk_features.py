
import os
import logging
from chatbot.llm import MultiProviderLLM
from dotenv import load_dotenv

# Load env
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_embeddings():
    logger.info("🧪 Testing Embeddings with google-genai SDK...")
    try:
        llm = MultiProviderLLM()
        text = "โรงเรียนสวนกุหลาบวิทยาลัย"
        
        logger.info(f"Generating embedding for: '{text}'")
        vector = llm.embed_content(text)
        
        if vector and len(vector) == 768:
            logger.info("✅ Embedding success! Vector length: 768")
        else:
            logger.error(f"❌ Embedding failed or invalid length. Length: {len(vector) if vector else 'None'}")
            
    except Exception as e:
        logger.error(f"❌ Embedding test exception: {e}")

def test_generate_content():
    logger.info("🧪 Testing Content Generation with google-genai SDK...")
    try:
        llm = MultiProviderLLM()
        prompt = "สวัสดีครับ แนะนำตัวหน่อย"
        
        logger.info(f"Generating content for: '{prompt}'")
        response = llm.generate_content(prompt)
        
        if response and response.text:
            logger.info(f"✅ Generation success! Response ({response.provider}): {response.text[:50]}...")
        else:
            logger.error("❌ Generation failed: Empty response")
            
    except Exception as e:
        logger.error(f"❌ Generation test exception: {e}")

def main():
    logger.info("🚀 Starting SDK Migration Tests")
    test_generate_content()
    test_embeddings()
    logger.info("🏁 Tests Completed")

if __name__ == "__main__":
    main()
