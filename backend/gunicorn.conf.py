# Gunicorn Configuration File
# Usage: gunicorn -c gunicorn.conf.py web_chatbot_v5:app

import multiprocessing
import os

# Server Socket
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:5001")
backlog = 2048

# Worker Processes
# ⚠️ Reduced from auto-calc to prevent memory issues with heavy Google/Firebase SDKs
workers = int(os.getenv("GUNICORN_WORKERS", 4))
worker_class = "gthread"  # 🔧 FIX: Use gthread for true multi-threading (was sync)
threads = int(os.getenv("GUNICORN_THREADS", 2))  # Each worker has 2 threads
worker_connections = 1000
max_requests = 1000  # Restart worker after 1000 requests (prevent memory leak)
max_requests_jitter = 50

# Timeout
timeout = 120  # LLM calls can be slow, allow up to 120 seconds
graceful_timeout = 30
keepalive = 5

# Logging
accesslog = "-"  # stdout
errorlog = "-"   # stderr
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sms'

# Process Naming
proc_name = "do-moe-chatbot"

# Server Mechanics
daemon = False  # Set to True for background running
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Hooks
def on_starting(server):
    print("="*70)
    print("🚀 DO-MOE Chatbot - Production Server Starting")
    print("="*70)

def on_exit(server):
    print("👋 DO-MOE Chatbot - Server Shutting Down")

def worker_exit(server, worker):
    print(f"🔄 Worker {worker.pid} exited, respawning...")

# Pre-load application for faster worker spawn
# ⚠️ DISABLED: preload_app causes SIGSEGV with Firebase/Google SDKs
# The Firebase SDK doesn't handle fork() well, causing segmentation faults
preload_app = False
