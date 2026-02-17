#!/usr/bin/env python3
"""
Seed Admin Config to Firestore
Reads existing keys from backend/.env and pushes them to Firestore settings/main-config
so the Admin Panel can display and manage them.

Usage: python3 scripts/seed_admin_config.py
"""
import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent / 'backend'
sys.path.insert(0, str(backend_dir))

def main():
    # Load .env manually
    env_path = backend_dir / '.env'
    env_vars = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                env_vars[key.strip()] = val.strip()
    
    gemini_key = env_vars.get('GEMINI_API_KEY', '')
    groq_key = env_vars.get('GROQ_API_KEY', '')
    
    if not gemini_key:
        print("❌ No GEMINI_API_KEY found in backend/.env")
        return
    
    # Skip placeholder groq keys
    if groq_key and 'your_' in groq_key.lower():
        groq_key = ''
        print("⚠️  GROQ_API_KEY is a placeholder, skipping")
    
    print(f"📦 Gemini key: {gemini_key[:12]}...{gemini_key[-4:]}")
    if groq_key:
        print(f"📦 Groq key: {groq_key[:8]}...{groq_key[-4:]}")
    
    # Initialize Firebase Admin
    service_account_path = backend_dir / 'serviceAccountKey.json'
    
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except ImportError:
        print("❌ firebase-admin not installed. Run: pip install firebase-admin")
        return
    
    try:
        firebase_admin.get_app()
    except ValueError:
        if service_account_path.exists():
            cred = credentials.Certificate(str(service_account_path))
            firebase_admin.initialize_app(cred)
            print(f"✅ Firebase initialized with {service_account_path.name}")
        else:
            print(f"❌ No {service_account_path.name} found")
            return
    
    db = firestore.client()
    
    # Build the config payload matching the AdminConfig schema
    api_keys_entry = {
        'geminiKeys': [gemini_key],
        'groqKeys': [groq_key] if groq_key else [],
        'geminiConnected': False,
        'groqConnected': False,
        'ragConnected': False,
        'flaskApiConnected': False,
        'flaskApiUrl': 'http://127.0.0.1:5001',
        'flaskApiEnabled': True,
        'ragEndpoint': '',
        'ragApiKey': '',
    }
    
    config_payload = {
        'apiKeys': {
            'general': api_keys_entry,
            'school': api_keys_entry,
            'student': api_keys_entry,
        }
    }
    
    # Merge into existing doc (don't overwrite prompts/model/etc)
    doc_ref = db.collection('settings').document('main-config')
    doc = doc_ref.get()
    
    if doc.exists:
        print("📄 Existing config found, merging API keys...")
        doc_ref.set(config_payload, merge=True)
    else:
        print("📄 No existing config, creating new document...")
        doc_ref.set(config_payload)
    
    print("✅ API keys seeded to Firestore settings/main-config!")
    print("   → Gemini keys: 1 key")
    if groq_key:
        print("   → Groq keys: 1 key")
    print("\n🔄 Now rebuild backend: docker compose -f docker-compose.prod.yml up -d --build backend")
    print("   Then refresh Admin Panel to see the keys.")

if __name__ == '__main__':
    main()
