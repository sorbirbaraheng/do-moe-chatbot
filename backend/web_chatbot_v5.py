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

# ---------------------------------------------------------------------
# Python 3.9 compatibility patch:
# Some dependencies expect importlib.metadata.packages_distributions (3.10+)
# ---------------------------------------------------------------------
try:
    import importlib.metadata as _importlib_metadata  # py3.8+
    if not hasattr(_importlib_metadata, "packages_distributions"):
        try:
            from importlib_metadata import packages_distributions as _packages_distributions  # backport
            _importlib_metadata.packages_distributions = _packages_distributions  # type: ignore[attr-defined]
        except Exception:
            # Fallback stub to avoid AttributeError in dependencies
            def _packages_distributions():
                return {}
            _importlib_metadata.packages_distributions = _packages_distributions  # type: ignore[attr-defined]
except Exception:
    pass

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
load_dotenv(dotenv_path=current_dir / ".env", override=False)

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
            for hist, _ in chatbot.chat(message, history, session_id=session_id):
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
    from datetime import datetime, timezone
    import base64
    import hashlib
    import hmac
    import json
    import time
    from werkzeug.security import check_password_hash

    app = Flask(__name__)

    allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "").strip()
    if allowed_origins_env:
        allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]
    else:
        # Default: restrict to common dev/local origins instead of wildcard
        allowed_origins = [
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
        ]

    CORS(app, resources={r"/.*": {"origins": allowed_origins}}, supports_credentials=True, send_wildcard=False)

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
        """Global CORS + Security header enforcement"""
        origin = request.headers.get('Origin', '')
        origin_allowed = False
        if origin:
            if origin in allowed_origins:
                origin_allowed = True
            else:
                try:
                    req_host = (request.host or "").split(":", 1)[0].strip().lower()
                    origin_host = (urlparse(origin).hostname or "").strip().lower()
                    if req_host and origin_host and req_host == origin_host:
                        origin_allowed = True
                except Exception:
                    origin_allowed = False

        if origin_allowed:
            response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization,X-API-Key'
        response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,OPTIONS'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        if 'Content-Type' not in response.headers:
            response.headers.add('Content-Type', 'application/json; charset=utf-8')  # Ensure Thai support

        # ── Security Headers ─────────────────────────────────────────
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(self), geolocation=()'
        # HSTS — only enforce when served over HTTPS
        if request.is_secure or request.headers.get('X-Forwarded-Proto') == 'https':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        # Content-Security-Policy — permissive enough for the SPA frontend
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://esm.sh https://cdn.tailwindcss.com https://fonts.googleapis.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https: blob:; "
            "connect-src 'self' https: wss:; "
            "media-src 'self' blob: data:; "
            "frame-ancestors 'none';"
        )

        return response
    
    if not qdrant_client:
        logger.error("Qdrant client not available")
        return None
    
    chatbot = EducationChatbot(qdrant_client)
    enable_debug_endpoints = os.getenv("ENABLE_DEBUG_ENDPOINTS", "0") == "1"

    # ------------------------------------------------------------------
    # Admin Auth + RBAC + Audit
    # ------------------------------------------------------------------
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
    ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH")
    OPERATOR_PASSWORD = os.getenv("OPERATOR_PASSWORD")
    OPERATOR_PASSWORD_HASH = os.getenv("OPERATOR_PASSWORD_HASH")
    VIEWER_PASSWORD = os.getenv("VIEWER_PASSWORD")
    VIEWER_PASSWORD_HASH = os.getenv("VIEWER_PASSWORD_HASH")
    ADMIN_TOKEN_SECRET = os.getenv("ADMIN_TOKEN_SECRET") or os.getenv("FLASK_SECRET_KEY")
    if not ADMIN_TOKEN_SECRET:
        logger.warning("⚠️ ADMIN_TOKEN_SECRET not set! Generating random secret (will change on restart)")
        import secrets
        ADMIN_TOKEN_SECRET = secrets.token_hex(32)
    ADMIN_TOKEN_TTL_SECONDS = int(os.getenv("ADMIN_TOKEN_TTL_SECONDS", "43200"))
    DISABLE_FIRESTORE = os.getenv("DISABLE_FIRESTORE", "0") == "1"

    ROLE_RANK = {"viewer": 0, "operator": 1, "admin": 2}

    def _check_password(password: str, plain_value: Optional[str], hashed_value: Optional[str]) -> bool:
        if hashed_value:
            try:
                return check_password_hash(hashed_value, password)
            except Exception:
                return False
        if plain_value:
            return hmac.compare_digest(password, plain_value)
        return False

    def _resolve_role(password: str) -> Optional[str]:
        if _check_password(password, ADMIN_PASSWORD, ADMIN_PASSWORD_HASH):
            return "admin"
        if _check_password(password, OPERATOR_PASSWORD, OPERATOR_PASSWORD_HASH):
            return "operator"
        if _check_password(password, VIEWER_PASSWORD, VIEWER_PASSWORD_HASH):
            return "viewer"
        return None

    def _b64encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

    def _b64decode(data: str) -> bytes:
        pad = "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(data + pad)

    def _sign(value: str) -> str:
        digest = hmac.new(ADMIN_TOKEN_SECRET.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).digest()
        return _b64encode(digest)

    def _create_token(role: str) -> str:
        now = int(time.time())
        payload = {"role": role, "iat": now, "exp": now + ADMIN_TOKEN_TTL_SECONDS}
        payload_str = json.dumps(payload, separators=(",", ":"))
        payload_b64 = _b64encode(payload_str.encode("utf-8"))
        signature = _sign(payload_b64)
        return f"{payload_b64}.{signature}"

    def _verify_token(token: str) -> Optional[dict]:
        try:
            payload_b64, signature = token.split(".", 1)
        except ValueError:
            return None
        expected_sig = _sign(payload_b64)
        if not hmac.compare_digest(signature, expected_sig):
            return None
        try:
            payload = json.loads(_b64decode(payload_b64))
        except Exception:
            return None
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload

    def _get_request_role() -> Optional[str]:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        token = auth_header.replace("Bearer ", "", 1).strip()
        payload = _verify_token(token)
        if not payload:
            return None
        return payload.get("role")

    def _require_role(min_role: str) -> tuple[Optional[str], Optional[tuple]]:
        role = _get_request_role()
        if not role:
            return None, (jsonify({"success": False, "error": "Unauthorized"}), 401)
        if ROLE_RANK.get(role, -1) < ROLE_RANK.get(min_role, 0):
            return role, (jsonify({"success": False, "error": "Forbidden"}), 403)
        return role, None

    def _get_client_ip() -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.remote_addr or "-"

    def _get_firestore_db():
        if DISABLE_FIRESTORE:
            return None
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore

            try:
                firebase_admin.get_app()
            except ValueError:
                service_account_path = Path(__file__).parent / "serviceAccountKey.json"
                if service_account_path.exists():
                    cred = credentials.Certificate(str(service_account_path))
                    firebase_admin.initialize_app(cred)
                else:
                    firebase_admin.initialize_app()
            return firestore.client()
        except Exception as e:
            logger.warning(f"⚠️ Firestore unavailable: {e}")
            return None

    def _write_shared_config(config_data: dict):
        config_path = Path(__file__).parent / 'shared_config.json'
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"⚠️ Failed to write shared_config.json: {e}")

    def _load_config_from_storage() -> dict:
        # Firestore first (if enabled)
        db = _get_firestore_db()
        if db:
            try:
                doc = db.collection("settings").document("main-config").get()
                if doc.exists:
                    return doc.to_dict() or {}
            except Exception as e:
                logger.warning(f"⚠️ Firestore config read failed: {e}")
        # Fallback shared_config.json
        config_path = Path(__file__).parent / 'shared_config.json'
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"⚠️ shared_config.json read failed: {e}")
        return {}

    def _merge_config(existing: dict, updates: dict) -> dict:
        merged = json.loads(json.dumps(existing or {}))
        for key, value in (updates or {}).items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key].update(value)
            else:
                merged[key] = value
        return merged

    def _redact_config(config_data: dict) -> dict:
        redacted = json.loads(json.dumps(config_data or {}))
        api_keys = redacted.get("apiKeys", {})
        for cat in ["general", "school", "student"]:
            cat_keys = api_keys.get(cat, {})
            for field in ["geminiKeys", "groqKeys"]:
                if isinstance(cat_keys.get(field), list):
                    cat_keys[field] = ["••••••"] * len(cat_keys[field])
            for field in ["embeddingApiKey", "ragApiKey", "pineconeApiKey", "flaskApiKey"]:
                if cat_keys.get(field):
                    cat_keys[field] = "••••••"
            api_keys[cat] = cat_keys
        redacted["apiKeys"] = api_keys
        return redacted

    def _summarize_config_update(payload: dict) -> dict:
        summary = {}
        if not payload:
            return summary

        if "apiKeys" in payload:
            summary["apiKeys"] = {}
            for cat, cat_payload in (payload.get("apiKeys") or {}).items():
                if not isinstance(cat_payload, dict):
                    continue
                summary["apiKeys"][cat] = {
                    "geminiKeys": len(cat_payload.get("geminiKeys") or []),
                    "groqKeys": len(cat_payload.get("groqKeys") or []),
                    "flaskApiUrl": bool(cat_payload.get("flaskApiUrl")),
                    "flaskApiEnabled": cat_payload.get("flaskApiEnabled"),
                    "ragEndpoint": bool(cat_payload.get("ragEndpoint")),
                }

        if "prompts" in payload:
            prompts = payload.get("prompts") or {}
            summary["prompts"] = {
                "version": prompts.get("version"),
                "languageStyle": prompts.get("languageStyle") or None,
            }

        if "model" in payload:
            model = payload.get("model") or {}
            summary["model"] = {
                "name": model.get("name"),
                "temperature": model.get("temperature"),
                "maxTokens": model.get("maxTokens"),
            }

        if "rag" in payload:
            summary["rag"] = payload.get("rag")

        if "uxPolicy" in payload:
            ux = payload.get("uxPolicy") or {}
            summary["uxPolicy"] = {
                "responseLength": ux.get("responseLength"),
                "languageStyle": ux.get("languageStyle"),
                "showRagDebug": ux.get("showRagDebug"),
            }

        return summary

    def _audit_log(action: str, status: str = "success", role: Optional[str] = None, detail: Optional[dict] = None):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "timestamp_ms": int(time.time() * 1000),
            "action": action,
            "status": status,
            "role": role or "-",
            "ip": _get_client_ip(),
            "path": request.path,
            "detail": detail or {},
        }

        db = _get_firestore_db()
        if db:
            try:
                db.collection("admin_audit").add(entry)
                return
            except Exception as e:
                logger.warning(f"⚠️ Firestore audit write failed: {e}")

        audit_path = Path(__file__).parent / "admin_audit.jsonl"
        try:
            with open(audit_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"⚠️ Audit file write failed: {e}")

    def _read_audit_logs(limit: int, cursor: Optional[str]):
        db = _get_firestore_db()
        if db:
            try:
                from google.cloud import firestore
                query = db.collection("admin_audit").order_by("timestamp_ms", direction=firestore.Query.DESCENDING).order_by("__name__", direction=firestore.Query.DESCENDING)
                if cursor:
                    try:
                        cursor_data = json.loads(_b64decode(cursor))
                        doc_id = cursor_data.get("id")
                        if doc_id:
                            doc = db.collection("admin_audit").document(doc_id).get()
                            if doc.exists:
                                query = query.start_after(doc)
                    except Exception:
                        pass
                docs = list(query.limit(limit + 1).stream())
                items = []
                for doc in docs[:limit]:
                    payload = doc.to_dict() or {}
                    payload["id"] = doc.id
                    items.append(payload)
                next_cursor = None
                has_more = len(docs) > limit
                if has_more and items:
                    last = items[-1]
                    next_cursor = _b64encode(json.dumps({"id": last.get("id")}).encode("utf-8"))
                return items, next_cursor, has_more
            except Exception as e:
                logger.warning(f"⚠️ Firestore audit read failed: {e}")

        audit_path = Path(__file__).parent / "admin_audit.jsonl"
        if audit_path.exists():
            try:
                with open(audit_path, "r", encoding="utf-8") as f:
                    lines = [json.loads(line) for line in f if line.strip()]
                lines.sort(key=lambda x: x.get("timestamp_ms", 0), reverse=True)
                start = int(cursor or 0)
                items = lines[start:start + limit]
                next_cursor = str(start + len(items)) if start + len(items) < len(lines) else None
                has_more = next_cursor is not None
                return items, next_cursor, has_more
            except Exception as e:
                logger.warning(f"⚠️ Audit file read failed: {e}")
        return [], None, False

    @app.route('/api/admin/login', methods=['POST', 'OPTIONS'])
    @limiter.exempt
    def admin_login():
        if request.method == 'OPTIONS':
            return '', 204
        data = request.json or {}
        password = data.get('password', '')
        role = _resolve_role(password)
        if not role:
            _audit_log("admin_login", status="failed", role="unknown", detail={"reason": "invalid_password"})
            return jsonify({'success': False, 'error': 'รหัสผ่านไม่ถูกต้อง'}), 401

        token = _create_token(role)
        _audit_log("admin_login", status="success", role=role)
        return jsonify({'success': True, 'token': token, 'role': role})

    @app.route('/api/admin/config', methods=['GET', 'POST', 'OPTIONS'])
    def admin_config():
        if request.method == 'OPTIONS':
            return '', 204

        role, error = _require_role('viewer')
        if error:
            return error

        if request.method == 'GET':
            config_data = _load_config_from_storage()
            if role == 'viewer':
                config_data = _redact_config(config_data)
            return jsonify({'success': True, 'config': config_data})

        # POST
        role, error = _require_role('operator')
        if error:
            return error

        payload = request.json or {}
        existing = _load_config_from_storage()
        merged = _merge_config(existing, payload)

        db = _get_firestore_db()
        if db and not DISABLE_FIRESTORE:
            try:
                db.collection("settings").document("main-config").set(payload, merge=True)
            except Exception as e:
                logger.warning(f"⚠️ Firestore config update failed: {e}")

        _write_shared_config(merged)
        _audit_log("admin_config_update", role=role, detail=_summarize_config_update(payload))
        return jsonify({'success': True})

    @app.route('/api/admin/audit', methods=['GET', 'OPTIONS'])
    def admin_audit():
        if request.method == 'OPTIONS':
            return '', 204

        role, error = _require_role('operator')
        if error:
            return error

        try:
            limit = int(request.args.get('limit', 20))
        except Exception:
            limit = 20
        cursor = request.args.get('cursor')

        logs, next_cursor, has_more = _read_audit_logs(limit, cursor)
        return jsonify({'success': True, 'logs': logs, 'nextCursor': next_cursor, 'hasMore': has_more})

    @app.route('/api/config/public', methods=['GET'])
    @limiter.exempt
    def public_config():
        config_data = _load_config_from_storage()
        config_data = _redact_config(config_data)
        return jsonify({'success': True, 'config': config_data})
    
    @app.route('/api/health', methods=['GET'])
    @limiter.exempt
    def health():
        return jsonify({'status': 'healthy', 'version': '5.0.0'})

    # ------------------------------------------------------------------
    # TTS — Edge TTS (Microsoft Neural) for น้องดีโอ voice
    # ------------------------------------------------------------------
    @app.route('/api/tts', methods=['POST', 'OPTIONS'])
    @limiter.limit("30 per minute")
    def tts():
        """Text-to-Speech using Edge TTS (Microsoft Neural voices)"""
        if request.method == 'OPTIONS':
            return '', 204

        import asyncio
        import base64
        import tempfile

        data = request.json or {}
        text = (data.get('text') or '').strip()
        if not text:
            return jsonify({'success': False, 'error': 'No text provided'}), 400

        # Truncate long text for performance
        if len(text) > 1000:
            text = text[:1000]

        # Voice config — น้องดีโอ = Thai male
        voice = data.get('voice', 'th-TH-NiwatNeural')
        rate = data.get('rate', '+5%')   # slightly faster = กระฉับกระเฉง
        pitch = data.get('pitch', '-20Hz')  # slightly deeper = ผู้ชาย (Hz format required)

        try:
            import edge_tts

            async def _generate():
                communicate = edge_tts.Communicate(
                    text=text,
                    voice=voice,
                    rate=rate,
                    pitch=pitch
                )
                tmp = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
                tmp_path = tmp.name
                tmp.close()
                await communicate.save(tmp_path)
                with open(tmp_path, 'rb') as f:
                    audio_data = f.read()
                import os
                os.unlink(tmp_path)
                return audio_data

            # Run async edge-tts in sync Flask context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                audio_bytes = loop.run_until_complete(_generate())
            finally:
                loop.close()

            audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
            logger.info(f"🔊 TTS generated: {len(text)} chars, voice={voice}, {len(audio_bytes)} bytes")

            return jsonify({
                'success': True,
                'audio': audio_b64,
                'format': 'mp3',
                'voice': voice,
                'text_length': len(text)
            })

        except ImportError:
            logger.error("❌ edge-tts not installed: pip install edge-tts")
            return jsonify({'success': False, 'error': 'TTS not available — edge-tts not installed'}), 500
        except Exception as e:
            logger.error(f"❌ TTS error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/cache/flush', methods=['POST', 'OPTIONS'])
    @limiter.exempt
    def cache_flush():
        """Flush all caches (Redis L1 + Qdrant semantic cache)"""
        if request.method == 'OPTIONS':
            return '', 204
        try:
            result = {"redis_deleted": 0, "semantic_deleted": 0}
            if hasattr(chatbot, 'cache') and chatbot.cache:
                result = chatbot.cache.flush()
            logger.info(f"🗑️ Cache flushed: {result}")
            return jsonify({'success': True, **result})
        except Exception as e:
            logger.error(f"❌ Cache flush error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/debug/route', methods=['POST', 'OPTIONS'])
    @limiter.exempt
    def debug_route():
        if request.method == 'OPTIONS':
            return '', 204
        if not enable_debug_endpoints:
            return jsonify({'error': 'debug endpoints disabled'}), 403

        data = request.json or {}
        message = data.get('message', '')
        session_id = data.get('session_id', 'debug')
        category = data.get('category', 'general')

        mem_data = session_db.get_session_data(session_id)
        if mem_data:
            memory = ConversationMemory.from_dict(mem_data)
        else:
            memory = ConversationMemory()

        chatbot.memory = memory
        chatbot._current_category = category

        try:
            context = memory.to_dict() if memory else {}
            tool_calls = chatbot.llm_agent._select_tools(message, context=context)
            return jsonify({'tool_calls': tool_calls})
        except Exception as e:
            logger.error(f"Debug route error: {e}")
            return jsonify({'error': str(e)}), 500

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
            def _normalize_name(name: str) -> str:
                return (name or "").replace("โรงเรียน", "").replace(" ", "")

            def _message_mentions_school(msg: str, name: str) -> bool:
                if not msg or not name:
                    return False
                msg_norm = msg.replace(" ", "")
                name_norm = _normalize_name(name)
                if name_norm and name_norm in msg_norm:
                    return True
                school_keywords = ["โรงเรียน", "วิทยาลัย", "สถาบัน", "มหาวิทยาลัย"]
                return any(k in msg for k in school_keywords)

            def _history_mentions_school(hist, name: str) -> bool:
                if not hist or not name:
                    return False
                name_norm = _normalize_name(name)
                for h in reversed(hist):
                    if isinstance(h, dict) and h.get("role") == "user":
                        content = (h.get("content") or "").replace(" ", "")
                        if name_norm and name_norm in content:
                            return True
                        break
                return False

            def _is_followup(msg: str) -> bool:
                if not msg:
                    return False
                follow_kws = ["แล้ว", "ต่อ", "อีก", "เพิ่ม", "ขอรายละเอียด", "รายละเอียด", "พิกัด", "ที่ไหน", "เบอร์ติดต่อ", "ครูกี่", "นักเรียนกี่", "ข้อมูล"]
                return len(msg) <= 24 and any(k in msg for k in follow_kws)

            def _is_aggregate_query(msg: str) -> bool:
                if not msg:
                    return False
                agg_kws = [
                    "จังหวัด", "ภาค", "อำเภอ", "เขต", "ตำบล", "แขวง",
                    "อันดับ", "มากที่สุด", "น้อยที่สุด", "สูงสุด", "ต่ำสุด",
                    "สรุป", "รวม", "ทั้งหมด", "ทั่วประเทศ"
                ]
                return any(k in msg for k in agg_kws)

            mentions_school = _message_mentions_school(message, school_name)
            is_followup = _is_followup(message)
            is_aggregate = _is_aggregate_query(message)

            # Only inject school context when it is clearly a school-specific follow-up.
            # Avoid injecting for aggregate/ranking/location queries.
            if is_aggregate and not mentions_school:
                should_inject = False
            else:
                should_inject = mentions_school or (is_followup and _history_mentions_school(history, school_name))

            if should_inject:
                memory.last_school_name = school_name
                logger.info(f"🏫 Injected school_name into memory: {school_name}")
            else:
                logger.info(f"🏫 Skipped frontend school_name injection (no match): {school_name}")
        
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
        for hist, _ in chatbot.chat(message, history, session_id=session_id):
            if hist:
                response_text = hist[-1].get('content', '')
        
        # 🆕 Store last AI response + detect disambiguation for next turn
        memory.last_ai_response = response_text
        memory.last_query = message
        import re
        disambig_markers = ["กรุณาเลือก", "พบโรงเรียน", "พบชื่อที่ตรงกัน", "ชื่อใกล้เคียง", "พบโรงเรียนที่ตรงกัน"]
        if any(marker in response_text for marker in disambig_markers):
            # Parse table to store structured choices (4 columns: idx, name, province, district)
            table_rows = re.findall(r'\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|', response_text)
            choices = []
            for idx_str, school_name, province, district in table_rows:
                try:
                    choices.append({"idx": int(idx_str), "name": school_name.strip(), "province": province.strip(), "district": district.strip()})
                except ValueError:
                    continue
            if choices:
                memory.last_disambig_choices = choices
                memory.last_disambig_query = message
                logger.info(f"📋 Stored {len(choices)} disambiguation choices for session {session_id}")
        else:
            # Clear disambiguation if response is not a table
            memory.last_disambig_choices = None
            memory.last_disambig_query = None

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
        role, error = _require_role('viewer')
        if error:
            return error
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
            _audit_log("admin_sessions_list", status="failed", role=role, detail={"error": str(e)})
            return jsonify({'success': False, 'error': str(e)})
    
    @app.route('/api/sync-config', methods=['POST', 'OPTIONS'])
    def sync_config():
        """Receives API keys from Admin Panel"""
        if request.method == 'OPTIONS':
            return '', 204

        role, error = _require_role('operator')
        if error:
            return error
        
        try:
            data = request.json
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400
            
            config_path = Path(__file__).parent / 'shared_config.json'
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ Config synced to {config_path}")
            _audit_log("sync_config", role=role, detail={"path": str(config_path)})
            return jsonify({
                'success': True, 
                'message': 'Config synced successfully',
                'path': str(config_path)
            })
        except Exception as e:
            logger.error(f"❌ Config sync failed: {e}")
            _audit_log("sync_config", status="failed", role=role, detail={"error": str(e)})
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

# =====================================================================
# GUNICORN WSGI ENTRY POINT
# =====================================================================
# For production deployment with Gunicorn:
#   gunicorn -c gunicorn.conf.py web_chatbot_v5:app
# 
# This creates the Flask app at module level so Gunicorn can import it
# =====================================================================
app = create_flask_api()
