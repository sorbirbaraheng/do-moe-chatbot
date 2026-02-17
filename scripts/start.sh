#!/bin/bash
# =============================================================================
# DO-MOE Chatbot — Start Production (Docker)
# =============================================================================
# Usage: ./scripts/start.sh           (build + start)
#        ./scripts/start.sh --no-build (start without rebuilding)
#        ./scripts/start.sh backend    (rebuild backend only)
# =============================================================================

set -euo pipefail
cd "$(dirname "$0")/.."

# Colors
G='\033[0;32m'; B='\033[0;34m'; Y='\033[1;33m'; R='\033[0;31m'; NC='\033[0m'

# Detect LAN IP
LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "localhost")

echo ""
echo -e "${B}======================================================${NC}"
echo -e "${B}🚀 DO-MOE Chatbot — Starting Production${NC}"
echo -e "${B}======================================================${NC}"

BUILD_FLAG="--build"
SERVICE=""

for arg in "$@"; do
  case "$arg" in
    --no-build) BUILD_FLAG="" ;;
    backend|frontend) SERVICE="$arg" ;;
  esac
done

# Start Docker Compose
echo -e "${Y}⏳ Starting Docker containers...${NC}"
docker compose -f docker-compose.prod.yml up -d $BUILD_FLAG $SERVICE

# Wait for backend health
echo -n -e "${Y}⏳ Waiting for backend health check...${NC}"
for i in {1..30}; do
  HTTP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5001/api/health 2>/dev/null || echo "000")
  if [ "$HTTP" = "200" ]; then
    echo -e " ${G}Ready!${NC}"
    break
  fi
  sleep 1
  echo -n "."
done

if [ "$HTTP" != "200" ]; then
  echo -e " ${R}Backend not responding (HTTP $HTTP)${NC}"
  echo -e "${Y}💡 Check logs: ./scripts/logs.sh backend${NC}"
fi

echo ""
echo -e "${G}======================================================${NC}"
echo -e "${G}✅ Services Started!${NC}"
echo -e "${G}======================================================${NC}"
echo ""
echo -e "   ${B}Frontend:${NC}  ${G}http://localhost:3001${NC}"
echo -e "   ${B}Backend:${NC}   ${G}http://localhost:5001${NC}"
echo -e "   ${B}LAN:${NC}       ${G}http://${LAN_IP}:3001${NC}"
echo ""
echo -e "   ${Y}📜 Logs:${NC}    ./scripts/logs.sh"
echo -e "   ${Y}📊 Status:${NC}  ./scripts/status.sh"
echo -e "   ${Y}🛑 Stop:${NC}    ./scripts/stop.sh"
echo ""
