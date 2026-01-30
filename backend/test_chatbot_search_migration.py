
import os
import sys
import logging
from unittest.mock import MagicMock, ANY
from qdrant_client import QdrantClient
from dotenv import load_dotenv

# Ensure backend path is in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from chatbot.chatbot_core import EducationChatbot
from chatbot.constants import COLLECTIONS

# Load env
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_chatbot_injection_logic():
    logger.info("🧪 Testing Chatbot Injection Logic (Mocked Qdrant)...")
    
    try:
        # Mock Qdrant Client
        client = MagicMock(spec=QdrantClient)
        
        # Mock get_collections to ensure Chatbot thinks DB is UP
        mock_collection = MagicMock()
        # Use one of the real collection names
        mock_collection.name = COLLECTIONS['schools'] # "edu_schools_v6" or similar
        client.get_collections.return_value.collections = [mock_collection]
        
        # Init Chatbot
        bot = EducationChatbot(client)
        
        # 1. Verify Deployment
        if bot.search_engine and bot.search_engine.llm_provider:
             logger.info("✅ SearchEngine instantiated with LLM Provider")
        else:
             logger.error("❌ SearchEngine MISSING LLM Provider")
             return

        # 2. Verify Embeddings Call uses LLM Provider
        logger.info("--- Verifying Semantic Search uses LLM Provider ---")
        
        # Spy on the llm_provider
        bot.model.embed_content = MagicMock(return_value=[0.1]*768) # Mock embedding response
        
        # Perform semantic search directly on engine to test logic
        bot.search_engine._semantic_search("test query", "test_collection", 5)
        
        if bot.model.embed_content.called:
             logger.info("✅ bot.model.embed_content() was CALLED by SearchEngine")
        else:
             logger.error("❌ bot.model.embed_content() was NOT CALLED")

    except Exception as e:
        logger.error(f"❌ Test Failed: {e}", exc_info=True)

if __name__ == "__main__":
    test_chatbot_injection_logic()
