#!/bin/bash
# =============================================================================
# DO-MOE Chatbot — Stop Production (Docker)
# =============================================================================
# Usage: ./scripts/stop.sh
# =============================================================================

cd "$(dirname "$0")/.."

echo "🛑 Stopping Production Services..."
docker compose -f docker-compose.prod.yml down

echo "✅ All services stopped."
