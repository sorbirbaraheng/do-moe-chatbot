
import sys
import os
import logging

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from backend.chatbot.llm import MultiProviderLLM

# Configure logging
logging.basicConfig(level=logging.INFO)

print("🔍 Debugging MultiProviderLLM Keys...")

try:
    # Test default initialization (category="school")
    llm = MultiProviderLLM(category="school")
    print(f"\n[Category: school]")
    print(f"Groq Keys: {len(llm.groq_keys)}")
    print(f"Keys: {llm.groq_keys}")
    
    # Test 'general' category
    llm2 = MultiProviderLLM(category="general")
    print(f"\n[Category: general]")
    print(f"Groq Keys: {len(llm2.groq_keys)}")
    print(f"Keys: {llm2.groq_keys}")

    # Test _reload_keys_if_needed logic explicitly
    print("\n[Testing Reload Logic]")
    llm._reload_keys_if_needed()
    print(f"After reload - Groq Keys: {len(llm.groq_keys)}")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
