#!/bin/bash
# DO-MOE Flask Backend Startup Script

cd /Users/sobirbaraheng/Downloads/chattt/moe-one---ict-hub/backend

# Kill existing Flask process
pkill -f "web_chatbot_v5.py" 2>/dev/null

# Wait a moment
sleep 2

# Start Flask in background with nohup
echo "🚀 Starting DO-MOE Flask Backend..."
nohup python3 web_chatbot_v5.py --api --host 0.0.0.0 --port 5001 > flask_server.log 2>&1 &

echo "✅ Flask started! PID: $!"
echo "📝 Log file: flask_server.log"
echo ""
echo "📍 Access URLs:"
echo "   Local:   http://localhost:5001"
echo "   Network: http://$(ipconfig getifaddr en0):5001"
