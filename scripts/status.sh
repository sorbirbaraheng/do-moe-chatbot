#!/bin/bash
# =============================================================================
# DO-MOE Chatbot — Service Status
# =============================================================================
# Usage: ./scripts/status.sh
# =============================================================================

cd "$(dirname "$0")/.."

# Colors
G='\033[0;32m'; B='\033[0;34m'; Y='\033[1;33m'; R='\033[0;31m'; NC='\033[0m'

LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "localhost")

echo ""
echo -e "${B}======================================================${NC}"
echo -e "${B}📊 DO-MOE Chatbot — Service Status${NC}"
echo -e "${B}======================================================${NC}"
echo ""

# Docker containers
echo -e "${B}🐳 Docker Containers:${NC}"
docker compose -f docker-compose.prod.yml ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo -e "   ${R}❌ Docker Compose not running${NC}"

echo ""

# Backend health check
echo -e "${B}🔧 Backend Health:${NC}"
HTTP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5001/api/health 2>/dev/null || echo "000")
if [ "$HTTP" = "200" ]; then
  echo -e "   ${G}✅ OK (HTTP 200)${NC}"
else
  echo -e "   ${R}❌ Unhealthy (HTTP $HTTP)${NC}"
fi

# Frontend check
echo -e "${B}🌐 Frontend:${NC}"
HTTP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3001 2>/dev/null || echo "000")
if [ "$HTTP" = "200" ]; then
  echo -e "   ${G}✅ OK (HTTP 200)${NC}"
else
  echo -e "   ${R}❌ Not responding (HTTP $HTTP)${NC}"
fi

echo ""
echo -e "${B}📍 Access URLs:${NC}"
echo -e "   Frontend: ${G}http://${LAN_IP}:3001${NC}"
echo -e "   Backend:  ${G}http://${LAN_IP}:5001${NC}"
echo ""
