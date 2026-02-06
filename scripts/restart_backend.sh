#!/bin/bash

# Define paths
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
LOG_FILE="$BACKEND_DIR/backend.log"

echo "🛑 Stopping Backend (web_chatbot_v5.py)..."
pkill -f "web_chatbot_v5.py" || echo "Backend not running."

echo "⏳ Waiting for port 5001 to clear..."
sleep 2

echo "🚀 Starting Backend on Port 5001..."
cd "$PROJECT_ROOT"
nohup python3 backend/web_chatbot_v5.py --api --port 5001 > "$LOG_FILE" 2>&1 &

PID=$!
echo "✅ Backend started with PID: $PID"
echo "📜 Tailing logs (Ctrl+C to exit log view, backend will keep running)..."
echo "===================================================================="
tail -f "$LOG_FILE"
