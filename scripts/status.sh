#!/bin/bash
# =============================================================================
# DO-MOE Chatbot - Check Service Status
# =============================================================================
# Usage: ./scripts/status.sh
# Shows status of backend (5001) and frontend (3001)
# =============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}📊 DO-MOE Chatbot - Service Status${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""

# Check Backend (port 5001)
echo -e "${BLUE}🔧 Backend (Port 5001):${NC}"
if lsof -Pi :5001 -sTCP:LISTEN -t >/dev/null 2>&1; then
    PID=$(lsof -ti:5001)
    echo -e "   ${GREEN}✅ RUNNING${NC} (PID: $PID)"
    
    # Try health check
    HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5001/api/health 2>/dev/null)
    if [ "$HEALTH" == "200" ]; then
        echo -e "   ${GREEN}✅ Health Check: OK${NC}"
    else
        echo -e "   ${YELLOW}⚠️  Health Check: HTTP $HEALTH${NC}"
    fi
else
    echo -e "   ${RED}❌ NOT RUNNING${NC}"
fi

echo ""

# Check Frontend (port 3001)
echo -e "${BLUE}🌐 Frontend (Port 3001):${NC}"
if lsof -Pi :3001 -sTCP:LISTEN -t >/dev/null 2>&1; then
    PID=$(lsof -ti:3001)
    echo -e "   ${GREEN}✅ RUNNING${NC} (PID: $PID)"
else
    echo -e "   ${RED}❌ NOT RUNNING${NC}"
fi

# Get local IP
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "localhost")

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📍 Access URLs:${NC}"
echo -e "   • Frontend: ${GREEN}http://$LOCAL_IP:3001${NC}"
echo -e "   • Backend:  ${GREEN}http://$LOCAL_IP:5001${NC}"
echo ""
