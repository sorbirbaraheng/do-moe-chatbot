#!/bin/bash
# =============================================================================
# DO-MOE Chatbot — View Docker Logs
# =============================================================================
# Usage: ./scripts/logs.sh             (all services, last 100 lines)
#        ./scripts/logs.sh backend     (backend only)
#        ./scripts/logs.sh frontend    (frontend only)
#        ./scripts/logs.sh -n 50       (last 50 lines)
# =============================================================================

cd "$(dirname "$0")/.."

SERVICE=""
LINES=100

while [[ $# -gt 0 ]]; do
  case "$1" in
    -n) LINES="$2"; shift 2 ;;
    backend|frontend) SERVICE="$1"; shift ;;
    *) shift ;;
  esac
done

echo "📜 Tailing logs (Ctrl+C to exit)..."
docker compose -f docker-compose.prod.yml logs -f --tail="$LINES" $SERVICE
