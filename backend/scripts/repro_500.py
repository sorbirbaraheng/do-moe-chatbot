
import sys
import os
import json
import logging

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from chatbot.chatbot_core import EducationChatbot
from chatbot.types import ParsedQuery
from qdrant_client import QdrantClient

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_repro():
    try:
        # Connect to Qdrant
        client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))
        bot = EducationChatbot(qdrant_client=client)
        executor = bot.llm_agent.tool_executor

        print("\n--- TEST 1: list_schools (Agency) ---")
        # Q: ขอรายชื่อโรงเรียนในสังกัด สพม.กรุงเทพมหานคร เขต 1 หน่อยครับ
        try:
            res1 = executor.execute("list_schools", {"agency": "สพม.กรุงเทพมหานคร เขต 1", "limit": 5})
            print(json.dumps(res1, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"❌ TEST 1 FAILED: {e}")
            import traceback
            traceback.print_exc()

        print("\n--- TEST 2: compare (School Typo) ---")
        try:
            res2 = executor.execute("compare", {"entity1": "เตรียมรีดม", "entity2": "สวนกุหลาบ", "metric": "students"})
            print(json.dumps(res2, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"❌ TEST 2 FAILED: {e}")
            import traceback
            traceback.print_exc()

        print("\n--- TEST 3: compare (Province Typo) ---")
        try:
            res3 = executor.execute("compare", {"entity1": "เชียงใหม่", "entity2": "เกัยงราย", "metric": "teachers"})
            print(json.dumps(res3, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"❌ TEST 3 FAILED: {e}")
            import traceback
            traceback.print_exc()

    except Exception as e:
        print(f"Critical Setup Error: {e}")

if __name__ == "__main__":
    run_repro()
