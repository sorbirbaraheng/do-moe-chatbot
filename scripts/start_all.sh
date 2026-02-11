#!/bin/bash
# =============================================================================
# DO-MOE Chatbot - Start All Services
# =============================================================================
# Location: /start_ascriptsll.sh
# Usage: ./scripts/start_all.sh (from project root)
# This script starts both Frontend (Next.js) and Backend (Gunicorn) services
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"  # Parent of scripts/
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR"

# Log files
BACKEND_LOG="$PROJECT_DIR/logs/backend.log"
FRONTEND_LOG="$PROJECT_DIR/logs/frontend.log"

# Create logs directory if not exists
mkdir -p "$PROJECT_DIR/logs"

echo ""
echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}🚀 DO-MOE Chatbot - Starting All Services${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""

# Function to check if port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to stop existing processes
stop_existing() {
    echo -e "${YELLOW}🔍 Checking for existing processes...${NC}"
    
    # Stop Backend (port 5001)
    if check_port 5001; then
        echo -e "${YELLOW}   ⚠️ Port 5001 in use - stopping existing backend...${NC}"
        lsof -ti:5001 | xargs kill -9 2>/dev/null || true
        sleep 1
    fi
    
    # Stop Frontend (port 3001)
    if check_port 3001; then
        echo -e "${YELLOW}   ⚠️ Port 3001 in use - stopping existing frontend...${NC}"
        lsof -ti:3001 | xargs kill -9 2>/dev/null || true
        sleep 1
    fi
    
    echo -e "${GREEN}   ✅ Ports cleared${NC}"
}

# Start Backend
start_backend() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}🔧 Starting Backend (Gunicorn)...${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    cd "$BACKEND_DIR"
    
    # Start Gunicorn in background
    nohup python3 -m gunicorn -c gunicorn.conf.py web_chatbot_v5:app > "$BACKEND_LOG" 2>&1 &
    BACKEND_PID=$!
    
    echo -e "   📝 Log: $BACKEND_LOG"
    echo -e "   🔗 URL: ${GREEN}http://0.0.0.0:5001${NC}"
    echo -e "   🆔 PID: $BACKEND_PID"
    
    # Wait for backend to start
    echo -n "   ⏳ Waiting for backend..."
    for i in {1..30}; do
        if check_port 5001; then
            echo -e " ${GREEN}Ready!${NC}"
            break
        fi
        sleep 1
        echo -n "."
    done
    
    if ! check_port 5001; then
        echo -e " ${RED}Failed!${NC}"
        echo -e "${RED}   ❌ Backend failed to start. Check logs: $BACKEND_LOG${NC}"
        exit 1
    fi
}

# Start Frontend
start_frontend() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}🌐 Starting Frontend (Next.js)...${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    cd "$FRONTEND_DIR"
    
    # Start Next.js in background
    nohup npm run dev > "$FRONTEND_LOG" 2>&1 &
    FRONTEND_PID=$!
    
    echo -e "   📝 Log: $FRONTEND_LOG"
    echo -e "   🔗 URL: ${GREEN}http://0.0.0.0:3001${NC}"
    echo -e "   🆔 PID: $FRONTEND_PID"
    
    # Wait for frontend to start
    echo -n "   ⏳ Waiting for frontend..."
    for i in {1..60}; do
        if check_port 3001; then
            echo -e " ${GREEN}Ready!${NC}"
            break
        fi
        sleep 1
        echo -n "."
    done
    
    if ! check_port 3001; then
        echo -e " ${RED}Failed!${NC}"
        echo -e "${RED}   ❌ Frontend failed to start. Check logs: $FRONTEND_LOG${NC}"
        exit 1
    fi
}

# Get local IP address
get_local_ip() {
    # Try to get the local IP address
    LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "localhost")
    echo "$LOCAL_IP"
}

# Main execution
stop_existing
start_backend
start_frontend

# Get local IP
LOCAL_IP=$(get_local_ip)

echo ""
echo -e "${GREEN}======================================================================${NC}"
echo -e "${GREEN}✅ All Services Started Successfully!${NC}"
echo -e "${GREEN}======================================================================${NC}"
echo ""
echo -e "📍 ${BLUE}Access URLs:${NC}"
echo -e "   • Frontend: ${GREEN}http://$LOCAL_IP:3001${NC}"
echo -e "   • Backend:  ${GREEN}http://$LOCAL_IP:5001${NC}"
echo -e "   • Health:   ${GREEN}http://$LOCAL_IP:5001/api/health${NC}"
echo ""
echo -e "📋 ${BLUE}Logs:${NC}"
echo -e "   • Backend:  tail -f $BACKEND_LOG"
echo -e "   • Frontend: tail -f $FRONTEND_LOG"
echo ""
echo -e "🛑 ${BLUE}To stop all services:${NC}"
echo -e "   $SCRIPT_DIR/stop_all.sh"
echo ""
echo -e "${YELLOW}💡 Tip: Press Ctrl+C to exit this script (services will keep running)${NC}"
echo ""
