#!/bin/bash
# DO-MOE Chatbot Production Startup Script
# Usage: ./start_production.sh

echo "🚀 Starting DO-MOE Chatbot in Production Mode..."

# Set environment
export PYTHONUNBUFFERED=1

# Kill any existing process on port 5001
lsof -ti:5001 | xargs kill -9 2>/dev/null

# Change to backend directory
cd "$(dirname "$0")"

# Check if gunicorn is installed
if ! command -v gunicorn &> /dev/null; then
    echo "❌ Gunicorn not found. Installing..."
    pip3 install gunicorn
fi

# Start with gunicorn
echo "✅ Starting Gunicorn with config..."
echo "   Workers: $(python3 -c 'import multiprocessing; print(multiprocessing.cpu_count() * 2 + 1)')"
echo "   Threads: 2"
echo "   Port: 5001"
echo ""

gunicorn -c gunicorn.conf.py web_chatbot_v5:app

# Alternative: Run in background
# nohup gunicorn -c gunicorn.conf.py web_chatbot_v5:app > logs/gunicorn.log 2>&1 &
# echo $! > gunicorn.pid
# echo "✅ Server started with PID $(cat gunicorn.pid)"
