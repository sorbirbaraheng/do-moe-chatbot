#!/bin/bash
# =============================================================================
# DO-MOE Chatbot - Restart Backend
# =============================================================================
# Usage: ./scripts/restart_backend.sh
# Auto-detects Docker vs Direct mode and restarts accordingly
# =============================================================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo ""
echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}🔄 DO-MOE Chatbot - Restarting Backend${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""

# Auto-detect: is Docker running our backend?
DOCKER_RUNNING=false
if docker compose -f "$PROJECT_DIR/docker-compose.prod.yml" ps --format '{{.Service}}' 2>/dev/null | grep -q "backend"; then
    DOCKER_RUNNING=true
fi

if [ "$DOCKER_RUNNING" = true ]; then
    # ==================== DOCKER MODE ====================
    echo -e "${YELLOW}🐳 Docker mode detected${NC}"
    echo -e "${YELLOW}🛑 Rebuilding & restarting backend container...${NC}"
    
    cd "$PROJECT_DIR"
    docker compose -f docker-compose.prod.yml up -d --build backend 2>&1 | tail -5
    
    # Wait for health check
    echo -n "   ⏳ Waiting for startup..."
    for i in {1..30}; do
        if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5001/api/health 2>/dev/null | grep -q "200"; then
            echo -e " ${GREEN}Ready!${NC}"
            break
        fi
        sleep 1
        echo -n "."
    done

    echo ""
    echo -e "${GREEN}✅ Backend Restarted (Docker)${NC}"
    echo -e "   🔗 URL: ${GREEN}http://localhost:5001${NC}"
    echo ""
    echo -e "${YELLOW}📜 Docker logs... (Ctrl+C to stop)${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    docker compose -f "$PROJECT_DIR/docker-compose.prod.yml" logs -f backend

else
    # ==================== DIRECT MODE ====================
    echo -e "${YELLOW}🐍 Direct Python mode${NC}"
    
    LOG_FILE="$PROJECT_DIR/logs/backend.log"
    mkdir -p "$PROJECT_DIR/logs"

    # Stop existing
    echo -e "${YELLOW}🛑 Stopping Backend (Port 5001)...${NC}"
    if lsof -Pi :5001 -sTCP:LISTEN -t >/dev/null 2>&1; then
        lsof -ti:5001 | xargs kill -9 2>/dev/null || true
        echo -e "${GREEN}   ✅ Killed process on port 5001${NC}"
    else
        echo -e "   ℹ️  Port 5001 is already free"
    fi
    pkill -9 -f "web_chatbot_v5.py" 2>/dev/null || true
    sleep 2

    # Start
    echo -e "${GREEN}🚀 Starting Backend...${NC}"
    cd "$PROJECT_DIR"
    nohup python3 backend/web_chatbot_v5.py --api --port 5001 > "$LOG_FILE" 2>&1 &

    # Wait for startup
    echo -n "   ⏳ Waiting for startup..."
    for i in {1..60}; do
        if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5001/api/health 2>/dev/null | grep -q "200"; then
            echo -e " ${GREEN}Ready!${NC}"
            break
        fi
        sleep 1
        echo -n "."
    done

    if ! lsof -Pi :5001 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e " ${RED}Failed!${NC}"
        tail -20 "$LOG_FILE"
        exit 1
    fi

    echo ""
    echo -e "${GREEN}✅ Backend Restarted (Direct)${NC}"
    echo -e "   🔗 URL: ${GREEN}http://0.0.0.0:5001${NC}"
    echo -e "   📝 Log: $LOG_FILE"
    echo ""
    echo -e "${YELLOW}📜 Tailing logs... (Ctrl+C to stop, backend keeps running)${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    tail -f "$LOG_FILE"
fi
