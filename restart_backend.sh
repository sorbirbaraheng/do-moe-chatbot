#!/bin/bash
# Refined restart script for backend

echo "🔄 Restarting Backend Service..."

# 1. Kill port 5001
echo "🧹 Killing processes on port 5001..."
lsof -i :5001 -t | xargs kill -9 2>/dev/null
pkill -f "web_chatbot_v5.py" 2>/dev/null
sleep 1

# 2. Check if port is free
PORT_CHECK=$(lsof -i :5001)
if [ -n "$PORT_CHECK" ]; then
    echo "❌ Port 5001 is still in use! Please check manually."
    exit 1
fi

# 3. Start Backend
echo "🚀 Starting web_chatbot_v5.py..."
cd backend
nohup python3 web_chatbot_v5.py --api --host 0.0.0.0 --port 5001 > flask_server.log 2>&1 &
PID=$!
echo "✅ Backend started with PID: $PID"
echo "📄 Logs: backend/flask_server.log"
