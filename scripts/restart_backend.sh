#!/bin/bash
# =============================================================================
# DO-MOE Chatbot - Restart Backend
# =============================================================================
# Usage: ./scripts/restart_backend.sh
# This script force-stops backend on port 5001 and restarts it
# =============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/logs/backend.log"

# Create logs directory
mkdir -p "$PROJECT_DIR/logs"

echo ""
echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}🔄 DO-MOE Chatbot - Restarting Backend${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""

# Force kill anything on port 5001
echo -e "${YELLOW}🛑 Stopping Backend (Port 5001)...${NC}"
if lsof -Pi :5001 -sTCP:LISTEN -t >/dev/null 2>&1; then
    lsof -ti:5001 | xargs kill -9 2>/dev/null || true
    echo -e "${GREEN}   ✅ Killed process on port 5001${NC}"
else
    echo -e "   ℹ️  Port 5001 is already free"
fi

# Also kill any lingering python processes
pkill -9 -f "web_chatbot_v5.py" 2>/dev/null || true
pkill -9 -f "gunicorn.*web_chatbot_v5" 2>/dev/null || true

# Wait for port to clear
echo -e "${YELLOW}⏳ Waiting for port to clear...${NC}"
sleep 2

# Verify port is free
if lsof -Pi :5001 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${RED}❌ Port 5001 still in use! Try: sudo lsof -ti:5001 | xargs kill -9${NC}"
    exit 1
fi

# Start backend
echo -e "${GREEN}🚀 Starting Backend...${NC}"
cd "$PROJECT_DIR"
nohup python3 backend/web_chatbot_v5.py --api --port 5001 > "$LOG_FILE" 2>&1 &
BACKEND_PID=$!

# Wait for startup (allow slower init)
echo -n "   ⏳ Waiting for startup..."
for i in {1..120}; do
    if lsof -Pi :5001 -sTCP:LISTEN -t >/dev/null 2>&1; then
        # Optional health check (non-blocking)
        if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5001/api/health | grep -q "200"; then
            echo -e " ${GREEN}Ready!${NC}"
            break
        fi
    fi
    sleep 1
    echo -n "."
done

# Check if started
if ! lsof -Pi :5001 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e " ${RED}Failed!${NC}"
    echo -e "${RED}❌ Backend failed to start. Last 20 lines of log:${NC}"
    tail -20 "$LOG_FILE"
    exit 1
fi

echo ""
echo -e "${GREEN}======================================================================${NC}"
echo -e "${GREEN}✅ Backend Restarted Successfully!${NC}"
echo -e "${GREEN}======================================================================${NC}"
echo ""
echo -e "   🔗 URL: ${GREEN}http://0.0.0.0:5001${NC}"
echo -e "   📝 Log: $LOG_FILE"
echo ""
echo -e "${YELLOW}📜 Tailing logs... (Ctrl+C to stop, backend keeps running)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
tail -f "$LOG_FILE"
