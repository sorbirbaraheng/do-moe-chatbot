"""
web_chatbot_v5.py - Production-Ready Smart Education Chatbot

📄 ชื่อไฟล์: web_chatbot_v5.py
📝 คำอธิบาย:
   ไฟล์หลักของ Backend Server (Flask Cloud Run / Local)
   ทำหน้าที่เป็น API Gateway รับส่งข้อมูลระหว่าง Frontend และระบบ AI

🛠 หน้าที่หลัก:
   1. API Server: ให้บริการ REST API สำหรับ Chat และการดึงข้อมูล
   2. Database Connector: เชื่อมต่อกับฐานข้อมูล Qdrant (Vector DB) และ SQLite (Session)
   3. AI Orchestrator: ควบคุมการทำงานของ Chatbot (รับข้อความ -> ค้นหาข้อมูล -> ตอบกลับ)
   4. Security: จัดการเรื่อง CORS และ Rate Limiting

🎯 Version 5.0 (Production - Refactored)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This file now serves as the entry point only с
All core logic has been modularized into the chatbot package.

Author: DO-MOE Education Team
Version: 5.0.0 (Refactored)
Last Updated: 2026-01-14
"""

import os
import logging
from pathlib import Path
from typing import Optional

# Third-party imports
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

# Session storage: Redis (production) with SQLite fallback
try:
    import redis_session as session_db  # Use Redis if available
except ImportError:
    import session_db  # Fallback to SQLite

# Import from modular chatbot package
from chatbot import (
    EducationChatbot,
    ConversationMemory,
    COLLECTIONS,
    input_sanitizer
)

try:
    import gradio as gr
    GRADIO_AVAILABLE = True
except ImportError:
    print("⚠️ Gradio not installed. Install: pip install gradio")
    GRADIO_AVAILABLE = False


# =====================================================================
# LOGGING CONFIGURATION
# =====================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# =====================================================================
# CONFIGURATION
# =====================================================================
current_dir = Path(__file__).parent
load_dotenv(dotenv_path=current_dir / ".env")

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")  # 8b has separate quota
QDRANT_URL = os.getenv("QDRANT_URL", "http://203.159.242.144:6333")
QDRANT_TIMEOUT = int(os.getenv("QDRANT_TIMEOUT", "5"))  # Lower timeout for fail-fast
# Initialize Gemini
if GEMINI_API_KEY:
    logger.info("✅ Gemini API Key preset")
else:
    logger.warning("⚠️ GEMINI_API_KEY not found (will rely on Firestore)")

# Initialize Groq
if GROQ_API_KEY and GROQ_API_KEY != "your_groq_api_key_here":
    logger.info(f"✅ Groq API configured - Model: {GROQ_MODEL}")
else:
    logger.info("ℹ️ Local GROQ_API_KEY not found - Will attempt to load from Cloud/Firestore")

# Initialize Qdrant
try:
    qdrant_client = QdrantClient(url=QDRANT_URL, timeout=QDRANT_TIMEOUT)
    logger.info(f"✅ Connected to Qdrant at {QDRANT_URL}")
except Exception as e:
    logger.error(f"❌ Failed to connect to Qdrant: {e}")
    qdrant_client = None

# Initialize Session DB
try:
    session_db.init_db()
except Exception as e:
    logger.error(f"Failed to init Session DB: {e}")


# =====================================================================
# GRADIO UI
# =====================================================================
def create_gradio_ui() -> Optional['gr.Blocks']:
    """Create Gradio interface"""
    if not GRADIO_AVAILABLE:
        logger.error("Gradio not available")
        return None
    
    if not qdrant_client:
        logger.error("Qdrant client not available")
        return None
    
    chatbot = EducationChatbot(qdrant_client)
    
    with gr.Blocks(title="🎓 DO-MOE Education Chatbot v5.0") as demo:
        gr.Markdown("""
        # 🎓 แชทบอท DO-MOE กระทรวงศึกษาธิการ v5.0
        ### ✨ Production Ready - รองรับทุกประเภทคำถาม
        """)
        
        with gr.Row():
            with gr.Column(scale=3):
                chatbox = gr.Chatbot(label="💬 การสนทนา", height=500, type="messages")
                
                with gr.Row():
                    msg = gr.Textbox(
                        placeholder="ถามอะไรก็ได้เกี่ยวกับโรงเรียนในไทย...",
                        scale=9, show_label=False, lines=1
                    )
                    submit = gr.Button("📤 ส่ง", variant="primary", scale=1)
                
                clear = gr.Button("🗑️ ล้างประวัติ", size="sm")
            
            with gr.Column(scale=1):
                gr.Markdown("""
                ### 💡 ตัวอย่างคำถาม
                
                **📊 นับจำนวน:**
                - ปัตตานีมีกี่โรงเรียน
                - ตำบลบานา อำเภอเมืองปัตตานี
                
                **🏆 มากที่สุด:**
                - ภาคใต้จังหวัดไหนมีโรงเรียนมากที่สุด
                - อำเภอไหนในยะลามีโรงเรียนเยอะสุด
                
                **🔽 น้อยที่สุด:**
                - ยะลาอำเภอไหนมีโรงเรียนน้อยที่สุด
                - ตำบลไหนมีโรงเรียนน้อยสุด
                
                **🔍 ค้นหา:**
                - เวียง เชียงแสน
                - ดอยลาน เมืองเชียงราย
                """)
        
        def respond(message, history):
            for hist, _ in chatbot.chat(message, history):
                yield hist, ""
        
        msg.submit(respond, [msg, chatbox], [chatbox, msg]).then(lambda: "", None, msg)
        submit.click(respond, [msg, chatbox], [chatbox, msg]).then(lambda: "", None, msg)
        clear.click(lambda: [], None, chatbox)
    
    return demo


# =====================================================================
# FLASK API
# =====================================================================
def create_flask_api():
    """Create Flask API for production deployment"""
    from flask import Flask, request, jsonify, Response, stream_with_context
    from flask_cors import CORS
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    import json

    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["1000 per day", "200 per hour"],
        storage_uri="memory://",
    )

    @app.errorhandler(429)
    def ratelimit_handler(e):
        return jsonify({
            "error": "ใจเย็นๆ นะครับ! คุณส่งข้อความเร็วเกินไป โปรดรอสักครู่ ⏳",
            "description": str(e.description)
        }), 429

    @app.after_request
    def after_request(response):
        """Global CORS header enforcement"""
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-API-Key')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Content-Type', 'application/json; charset=utf-8') # Ensure Thai support
        return response
    
    if not qdrant_client:
        logger.error("Qdrant client not available")
        return None
    
    chatbot = EducationChatbot(qdrant_client)
    
    @app.route('/api/health', methods=['GET'])
    @limiter.exempt
    def health():
        return jsonify({'status': 'healthy', 'version': '5.0.0'})

    @app.route('/api/chat/stream', methods=['POST', 'OPTIONS'])
    @limiter.limit("60 per minute")
    def chat_stream():
        if request.method == 'OPTIONS':
            return '', 204
        """Stream chat response (Server-Sent Events)"""
        data = request.json
        message = data.get('message', '')
        history = data.get('history', [])
        session_id = data.get('session_id', 'default')
        category = data.get('category', 'general')
        
        # NEW: Extract parsed query metadata from frontend
        intent = data.get('intent')
        school_name = data.get('school_name')
        level = data.get('level')
        
        if intent:
            logger.info(f"📥 Received parsed metadata - Intent: {intent}, School: {school_name}, Level: {level}")

        # Load persistence
        mem_data = session_db.get_session_data(session_id)
        if mem_data:
            memory = ConversationMemory.from_dict(mem_data)
        else:
            memory = ConversationMemory()
        
        # If frontend parsed a school_name, inject it into memory for better routing
        if school_name:
            memory.last_school_name = school_name
            logger.info(f"🏫 Injected school_name into memory: {school_name}")
        
        # NEW: Inject frontend-provided level for correct collection routing
        if level:
            memory.frontend_level = level
            logger.info(f"📊 Injected frontend_level into memory: {level}")
        
        chatbot.memory = memory
        chatbot._current_category = category
        
        def generate():
            last_len = 0
            if not memory.last_province and history:
                memory.extract_from_history(history)
                
            for hist, _ in chatbot.chat(message, history):
                if hist:
                    content = hist[-1].get('content', '')
                    delta = content[last_len:]
                    if delta:
                        yield f"data: {json.dumps({'text': delta}, ensure_ascii=False)}\n\n"
                        last_len = len(content)
            
            session_db.save_session_data(session_id, memory.to_dict())
            yield "data: [DONE]\n\n"
            
        return Response(stream_with_context(generate()), mimetype='text/event-stream')
    
    @app.route('/api/chat', methods=['POST'])
    @limiter.limit("20 per minute")
    def chat():
        data = request.json
        message = data.get('message', '')
        history = data.get('history', [])
        session_id = data.get('session_id', 'default')
        category = data.get('category', 'general')
        
        mem_data = session_db.get_session_data(session_id)
        if mem_data:
            memory = ConversationMemory.from_dict(mem_data)
        else:
            memory = ConversationMemory()
            logger.info(f"🆕 Created new session memory: {session_id}")
        
        if not memory.last_province and history:
            memory.extract_from_history(history)
            logger.info(f"📚 Extracted context from history: {memory}")
        
        chatbot.memory = memory
        chatbot._current_category = category
        
        response_text = ""
        for hist, _ in chatbot.chat(message, history):
            if hist:
                response_text = hist[-1].get('content', '')
        
        logger.info(f"💾 Session {session_id} memory after chat: {memory}")
        session_db.save_session_data(session_id, memory.to_dict())
        
        return jsonify({
            'success': True,
            'response': response_text,
            'history': hist,
            'memory': {
                'province': memory.last_province,
                'district': memory.last_district,
                'agency': memory.last_agency
            }
        })

    @app.route('/api/sessions', methods=['GET'])
    def list_sessions():
        """Admin endpoint to list all active sessions"""
        try:
            limit = request.args.get('limit', 50)
            conn = session_db.sqlite3.connect(session_db.DB_PATH)
            conn.row_factory = session_db.sqlite3.Row
            c = conn.cursor()
            
            c.execute("""
                SELECT session_id, memory_json, updated_at 
                FROM sessions 
                ORDER BY updated_at DESC 
                LIMIT ?
            """, (limit,))
            
            rows = c.fetchall()
            conn.close()
            
            results = []
            for row in rows:
                mem = json.loads(row['memory_json'])
                results.append({
                    'id': row['session_id'],
                    'updated_at': row['updated_at'],
                    'province': mem.get('last_province'),
                    'agency': mem.get('last_agency'),
                    'last_query': mem.get('last_query')
                })
                
            return jsonify({'success': True, 'sessions': results})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    
    @app.route('/api/sync-config', methods=['POST', 'OPTIONS'])
    def sync_config():
        """Receives API keys from Admin Panel"""
        if request.method == 'OPTIONS':
            return '', 204
        
        try:
            data = request.json
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400
            
            config_path = Path(__file__).parent / 'shared_config.json'
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ Config synced to {config_path}")
            return jsonify({
                'success': True, 
                'message': 'Config synced successfully',
                'path': str(config_path)
            })
        except Exception as e:
            logger.error(f"❌ Config sync failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/schools/list', methods=['POST', 'OPTIONS'])
    def schools_list():
        """Paginated school list - queries Qdrant directly"""
        if request.method == 'OPTIONS':
            return '', 204
        
        try:
            data = request.json or {}
            province = data.get('province')
            district = data.get('district')
            agency = data.get('agency')
            offset = data.get('offset', 0)
            limit = data.get('limit', 15)
            
            if not province:
                return jsonify({'success': False, 'error': 'Province is required'}), 400
            
            conditions = [
                FieldCondition(key="metadata.province", match=MatchValue(value=province))
            ]
            if agency:
                conditions.append(
                    FieldCondition(key="metadata.agency", match=MatchValue(value=agency))
                )
            if district:
                conditions.append(
                    FieldCondition(key="metadata.district", match=MatchValue(value=district))
                )
            
            scroll_filter = Filter(must=conditions)
            all_unique_codes = set()
            unique_schools = []
            scroll_offset = None
            
            while True:
                response = qdrant_client.scroll(
                    collection_name=COLLECTIONS["schools"],
                    scroll_filter=scroll_filter,
                    offset=scroll_offset,
                    limit=500,
                    with_payload=True
                )
                points, next_offset = response
                
                if not points:
                    break
                    
                for point in points:
                    meta = point.payload.get('metadata', {})
                    code = meta.get('school_code')
                    if code and code not in all_unique_codes:
                        all_unique_codes.add(code)
                        unique_schools.append({
                            'name': meta.get('school_name', 'ไม่ระบุ'),
                            'province': meta.get('province', '-'),
                            'district': meta.get('district', '-'),
                            'subdistrict': meta.get('subdistrict', '-'),
                            'agency': meta.get('agency', '-'),
                        })
                
                if next_offset is None:
                    break
                scroll_offset = next_offset
            
            total = len(unique_schools)
            paged_schools = unique_schools[offset:offset + limit]
            
            return jsonify({
                'success': True,
                'schools': paged_schools,
                'total': total,
                'offset': offset,
                'limit': limit,
                'hasMore': offset + len(paged_schools) < total,
                'query': {
                    'province': province,
                    'district': district,
                    'agency': agency
                }
            })
            
        except Exception as e:
            logger.error(f"❌ Schools list error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    

    @app.route('/api/admin/upload', methods=['POST', 'OPTIONS'])
    def admin_upload():
        """Handle file upload for admin data sync"""
        if request.method == 'OPTIONS':
            return '', 204
        
        try:
            if 'file' not in request.files:
                return jsonify({'success': False, 'error': 'No file part'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'success': False, 'error': 'No selected file'}), 400
            
            if file:
                import werkzeug
                filename = werkzeug.utils.secure_filename(file.filename)
                
                # Ensure upload dir exists
                upload_dir = current_dir / "uploads"
                upload_dir.mkdir(exist_ok=True)
                
                file_path = upload_dir / filename
                file.save(str(file_path))
                
                logger.info(f"✅ File uploaded: {file_path}")
                return jsonify({
                    'success': True, 
                    'message': 'File uploaded successfully',
                    'filename': filename
                })
                
        except Exception as e:
            logger.error(f"❌ Upload failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/admin/reindex', methods=['POST', 'OPTIONS'])
    def admin_reindex():
        """Trigger re-indexing process"""
        if request.method == 'OPTIONS':
            return '', 204
            
        try:
            data = request.json or {}
            target = data.get('target', 'all')
            
            logger.info(f"🔄 Re-index triggered for: {target}")
            
            # Run in background thread to avoid blocking API
            import threading
            from scripts.reindex_v6 import reindex_data
            
            def run_reindex():
                try:
                    logger.info("🚀 Starting background re-index task...")
                    reindex_data()
                    logger.info("✅ Background re-index completed")
                except Exception as e:
                    logger.error(f"❌ Background re-index failed: {e}")
            
            thread = threading.Thread(target=run_reindex)
            thread.daemon = True
            thread.start()
            
            return jsonify({
                'success': True,
                'message': f'Re-indexing process started for {target}'
            })
            
        except Exception as e:
            logger.error(f"❌ Re-index trigger failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    return app


# =====================================================================
# MAIN
# =====================================================================
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="DO-MOE Education Chatbot v5.0")
    parser.add_argument('--port', type=int, default=7860)
    parser.add_argument('--host', type=str, default="0.0.0.0")
    parser.add_argument('--share', action='store_true')
    parser.add_argument('--api', action='store_true', help='Run as Flask API')
    
    args = parser.parse_args()
    
    if not GEMINI_API_KEY:
        logger.error("❌ GEMINI_API_KEY not found!")
        return
    
    print(f"""
{'='*80}
🚀 DO-MOE Education Chatbot v5.0 (Production - Refactored)
{'='*80}

✅ Features:
   - Full Query Support (มากที่สุด/น้อยที่สุด/เปรียบเทียบ)
   - Smart Entity Extraction (จังหวัด/อำเภอ/ตำบล)
   - Fuzzy Matching (ค้นหาใกล้เคียง)
   - Production-grade Error Handling
   - 🆕 Modular Architecture (Refactored)

🌐 Server: {args.host}:{args.port}
{'='*80}
    """)
    
    if args.api:
        app = create_flask_api()
        if app:
            app.run(host=args.host, port=args.port)
    else:
        demo = create_gradio_ui()
        if demo:
            demo.launch(
                server_name=args.host,
                server_port=args.port,
                share=args.share,
                show_error=True
            )


if __name__ == "__main__":
    main()
