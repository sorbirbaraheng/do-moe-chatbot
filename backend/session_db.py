
import sqlite3
import json
import time
import os
from typing import Optional, Dict, Any

# Ensure we write to current directory or specified payload path
DB_PATH = os.environ.get("SESSION_DB_PATH", "sessions.db")

def init_db():
    """Initialize the session database table"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                memory_json TEXT,
                updated_at REAL
            )
        ''')
        # Index for cleanup (optional)
        c.execute('CREATE INDEX IF NOT EXISTS idx_updated_at ON sessions(updated_at)')
        conn.commit()
        conn.close()
        print(f"✅ Session Database initialized at {DB_PATH}")
    except Exception as e:
        print(f"❌ Failed to init DB: {e}")

def get_session_data(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve session memory dictionary by ID"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT memory_json FROM sessions WHERE session_id = ?", (session_id,))
        row = c.fetchone()
        conn.close()
        
        if row:
            return json.loads(row[0])
    except Exception as e:
        print(f"⚠️ DB Read Error: {e}")
    return None

def save_session_data(session_id: str, memory_data: Dict[str, Any]):
    """Save or update session memory"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        json_str = json.dumps(memory_data, ensure_ascii=False)
        timestamp = time.time()
        
        c.execute("""
            INSERT OR REPLACE INTO sessions (session_id, memory_json, updated_at)
            VALUES (?, ?, ?)
        """, (session_id, json_str, timestamp))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ DB Write Error: {e}")

def cleanup_old_sessions(days=7):
    """Remove sessions older than X days"""
    try:
        cutoff = time.time() - (days * 86400)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM sessions WHERE updated_at < ?", (cutoff,))
        deleted = c.rowcount
        conn.commit()
        conn.close()
        if deleted > 0:
            print(f"🧹 Cleaned up {deleted} old sessions")
    except Exception as e:
        print(f"⚠️ Cleanup Error: {e}")
