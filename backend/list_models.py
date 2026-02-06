import os
import sys
from dotenv import load_dotenv
from google import genai

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
# Explicitly load .env from parent directory
env_path = os.path.join(os.path.dirname(__file__), '../.env')
print(f"📂 Loading .env from: {os.path.abspath(env_path)}")
load_dotenv(env_path)

def list_models():
    api_key = os.getenv("GEMINI_API_KEY")
    # Debug: Check other keys if main one missing
    if not api_key:
         api_key = os.getenv("GOOGLE_API_KEY")
         
    if not api_key:
        print("❌ No API key found in env vars")
        return

    client = genai.Client(api_key=api_key)
    try:
        print("🔍 Listing models...")
        for m in client.models.list(config={"page_size": 100}):
            if "embed" in m.name:
                print(f" - {m.name} ({m.display_name})")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    list_models()
