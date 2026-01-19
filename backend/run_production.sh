#!/bin/bash

# ==========================================
# DO-MOE Production Runner (Gunicorn)
# ==========================================

PORT=7860
WORKERS=4           # Standard calculation: (2 x CPU Cores) + 1
TIMEOUT=120         # Timeout in seconds
MODULE="web_chatbot_v5:create_flask_api()"

echo "🤖 DO-MOE Chatbot: Starting Production Mode..."

# 1. Check Python environment
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 could not be found."
    exit 1
fi

# 2. Check/Install Dependencies
echo "📦 Checking essential packages..."
# Use pip3 explicitly
pip3 install gunicorn flask-limiter flask-cors qdrant-client google-generativeai --quiet

if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies. Trying simple command..."
    # Fallback if quiet fails or something
    pip3 install gunicorn flask-limiter flask-cors
fi

# 3. Start Server
PORT_PID=$(lsof -t -i:$PORT)
if [ -n "$PORT_PID" ]; then
    echo "🧹 Freeing port $PORT (PID: $PORT_PID)..."
    kill -9 $PORT_PID
    sleep 1 # Give it a second to die
fi

echo "🚀 Launching Gunicorn with $WORKERS workers on port $PORT..."
echo "   (Press Ctrl+C to stop)"
echo "---------------------------------------------------"

# Run Gunicorn via python3 module to ensure path is correct
exec python3 -m gunicorn -w $WORKERS \
    -b 0.0.0.0:$PORT \
    --timeout $TIMEOUT \
    --access-logfile - \
    --error-logfile - \
    --worker-class sync \
    "$MODULE"
