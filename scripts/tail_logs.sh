#!/bin/bash
# =============================================================================
# DO-MOE Chatbot - Tail Logs
# =============================================================================
# Usage: ./scripts/tail_logs.sh [backend|frontend|all]
# Default: backend
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
BACKEND_LOG="$PROJECT_DIR/logs/backend.log"
FRONTEND_LOG="$PROJECT_DIR/logs/frontend.log"

# Create logs directory
mkdir -p "$PROJECT_DIR/logs"

# Parse argument
MODE="${1:-backend}"

echo ""
echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}📜 DO-MOE Chatbot - Tail Logs${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""

case "$MODE" in
    backend)
        echo -e "${GREEN}📋 Tailing Backend Log: $BACKEND_LOG${NC}"
        echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
        echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        if [ -f "$BACKEND_LOG" ]; then
            tail -f "$BACKEND_LOG"
        else
            echo -e "${RED}❌ Log file not found: $BACKEND_LOG${NC}"
            echo -e "   Start the backend first with: ./scripts/restart_backend.sh"
            exit 1
        fi
        ;;
    frontend)
        echo -e "${GREEN}📋 Tailing Frontend Log: $FRONTEND_LOG${NC}"
        echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
        echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        if [ -f "$FRONTEND_LOG" ]; then
            tail -f "$FRONTEND_LOG"
        else
            echo -e "${RED}❌ Log file not found: $FRONTEND_LOG${NC}"
            echo -e "   Start the frontend first with: ./scripts/start_all.sh"
            exit 1
        fi
        ;;
    all)
        echo -e "${GREEN}📋 Tailing All Logs${NC}"
        echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
        echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        
        # Check if files exist
        if [ ! -f "$BACKEND_LOG" ] && [ ! -f "$FRONTEND_LOG" ]; then
            echo -e "${RED}❌ No log files found!${NC}"
            echo -e "   Start services first with: ./scripts/start_all.sh"
            exit 1
        fi
        
        # Tail both files
        tail -f "$BACKEND_LOG" "$FRONTEND_LOG" 2>/dev/null
        ;;
    *)
        echo -e "${RED}❌ Unknown mode: $MODE${NC}"
        echo ""
        echo "Usage: $0 [backend|frontend|all]"
        echo ""
        echo "  backend  - Tail backend logs (default)"
        echo "  frontend - Tail frontend logs"
        echo "  all      - Tail both logs"
        exit 1
        ;;
esac
