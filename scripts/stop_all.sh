#!/bin/bash
# =============================================================================
# DO-MOE Chatbot - Stop All Services
# =============================================================================
# Usage: ./scripts/stop_all.sh
# This script stops both Frontend (Next.js) and Backend (Gunicorn) services
# =============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}🛑 DO-MOE Chatbot - Stopping All Services${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""

# Function to stop process on port
stop_port() {
    local port=$1
    local name=$2
    
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${YELLOW}   Stopping $name on port $port...${NC}"
        lsof -ti:$port | xargs kill -9 2>/dev/null || true
        echo -e "${GREEN}   ✅ $name stopped${NC}"
    else
        echo -e "   ℹ️ $name not running on port $port"
    fi
}

# Stop Backend (port 5001)
stop_port 5001 "Backend (Gunicorn)"

# Stop Frontend (port 3001)  
stop_port 3001 "Frontend (Next.js)"

echo ""
echo -e "${GREEN}======================================================================${NC}"
echo -e "${GREEN}✅ All Services Stopped${NC}"
echo -e "${GREEN}======================================================================${NC}"
echo ""
