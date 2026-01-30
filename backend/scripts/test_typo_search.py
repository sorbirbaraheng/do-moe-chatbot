
import os
import sys
import json

# Add backend directory to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from chatbot.chatbot_core import EducationChatbot
from qdrant_client import QdrantClient

def test_typo():
    # Initialize Qdrant
    qdrant_url = os.getenv("QDRANT_URL", "http://203.159.242.144:6333")
    client = QdrantClient(url=qdrant_url)
    
    bot = EducationChatbot(qdrant_client=client)
    
    # 1. Typo: Missing vowel "า" -> สตรีวิทย
    query_typo = "สตรีวิทย" 
    print(f"🔍 Testing Typo Query: '{query_typo}' (Target: สตรีวิทยา)")
    
    # Use the tool executor directly to see raw output
    res = bot.llm_agent.tool_executor._get_school_full_details(school_name=query_typo)
    
    print(json.dumps(res, indent=2, ensure_ascii=False))
    
    # 2. Typo: Wrong char "พัานาการ" -> พัฒนาการ
    query_typo_2 = "เตรียมอุดมพัานาการ"
    print(f"\n🔍 Testing Typo Query: '{query_typo_2}' (Target: เตรียมอุดมพัฒนาการ)")
    res2 = bot.llm_agent.tool_executor._get_school_full_details(school_name=query_typo_2)
    print(json.dumps(res2, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    test_typo()
