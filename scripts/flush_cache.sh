#!/bin/bash
# =============================================================================
# DO-MOE Chatbot - Flush Cache (Redis L1 + Qdrant semantic_cache)
# =============================================================================
# Usage:
#   ./scripts/flush_cache.sh
#   ./scripts/flush_cache.sh --redis-only
#   ./scripts/flush_cache.sh --semantic-only
#   ./scripts/flush_cache.sh --yes
# =============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/backend/.env"

ONLY_REDIS=0
ONLY_SEMANTIC=0
AUTO_YES=0

for arg in "$@"; do
  case "$arg" in
    --redis-only) ONLY_REDIS=1 ;;
    --semantic-only) ONLY_SEMANTIC=1 ;;
    --yes|-y) AUTO_YES=1 ;;
  esac
done

if [[ $ONLY_REDIS -eq 1 && $ONLY_SEMANTIC -eq 1 ]]; then
  echo -e "${RED}❌ เลือกได้อย่างใดอย่างหนึ่ง: --redis-only หรือ --semantic-only${NC}"
  exit 1
fi

# Load env safely (do NOT eval/expand $VAR in values)
if [[ -f "$ENV_FILE" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    # Trim CR (Windows)
    line="${line%$'\r'}"
    # Skip blanks/comments
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
      key="${BASH_REMATCH[1]}"
      val="${BASH_REMATCH[2]}"
      # Strip surrounding quotes
      if [[ "$val" =~ ^\".*\"$ ]]; then
        val="${val:1:${#val}-2}"
      elif [[ "$val" =~ ^\'.*\'$ ]]; then
        val="${val:1:${#val}-2}"
      fi
      export "$key=$val"
    fi
  done < "$ENV_FILE"
fi

REDIS_URL="${REDIS_URL:-}"
QDRANT_URL="${QDRANT_URL:-}"
QDRANT_TIMEOUT="${QDRANT_TIMEOUT:-60}"

confirm() {
  local prompt="$1"
  if [[ $AUTO_YES -eq 1 ]]; then
    return 0
  fi
  read -r -p "$prompt [y/N]: " ans
  [[ "$ans" =~ ^[Yy]$ ]]
}

echo ""
echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}🧹 DO-MOE Chatbot - Flush Cache${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""

do_redis=1
do_semantic=1
if [[ $ONLY_REDIS -eq 1 ]]; then
  do_semantic=0
fi
if [[ $ONLY_SEMANTIC -eq 1 ]]; then
  do_redis=0
fi

if [[ $do_redis -eq 1 ]]; then
  if [[ -z "$REDIS_URL" ]]; then
    echo -e "${YELLOW}⚠️  REDIS_URL not set - skipping Redis cache flush${NC}"
  else
    echo -e "${YELLOW}🧹 Redis L1 Cache${NC}"
    if confirm "ล้าง Redis cache หรือไม่?"; then
      if command -v redis-cli >/dev/null 2>&1; then
        redis-cli -u "$REDIS_URL" FLUSHDB >/dev/null && \
          echo -e "${GREEN}✅ Redis cache cleared${NC}" || \
          echo -e "${RED}❌ Redis flush failed${NC}"
      else
        python3 - <<'PY' || echo -e "${RED}❌ Redis flush failed (python)${NC}"
import os
try:
    import redis
except Exception as e:
    print("redis module not available:", e)
    raise SystemExit(1)

url = os.environ.get("REDIS_URL")
if not url:
    print("REDIS_URL not set")
    raise SystemExit(1)

r = redis.from_url(url, decode_responses=True)
r.flushdb()
print("Redis cache cleared")
PY
      fi
    else
      echo -e "${YELLOW}⏭️  Skipped Redis cache${NC}"
    fi
  fi
fi

if [[ $do_semantic -eq 1 ]]; then
  if [[ -z "$QDRANT_URL" ]]; then
    echo -e "${YELLOW}⚠️  QDRANT_URL not set - skipping semantic_cache flush${NC}"
  else
    echo ""
    echo -e "${YELLOW}🧹 Qdrant semantic_cache${NC}"
    if confirm "ล้าง semantic_cache ใน Qdrant หรือไม่?"; then
      python3 - <<'PY' || echo -e "${RED}❌ Qdrant semantic_cache flush failed${NC}"
import os
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter

url = os.environ.get("QDRANT_URL")
timeout = float(os.environ.get("QDRANT_TIMEOUT", "60"))
collection = "semantic_cache"

client = QdrantClient(url=url, timeout=timeout)
collections = [c.name for c in client.get_collections().collections]
if collection not in collections:
    print("semantic_cache collection not found - skip")
    raise SystemExit(0)

# Delete all points in semantic_cache
client.delete(
    collection_name=collection,
    points_selector=Filter()
)
print("semantic_cache cleared")
PY
      echo -e "${GREEN}✅ semantic_cache cleared${NC}"
    else
      echo -e "${YELLOW}⏭️  Skipped semantic_cache${NC}"
    fi
  fi
fi

echo ""
echo -e "${GREEN}======================================================================${NC}"
echo -e "${GREEN}✅ Cache flush completed${NC}"
echo -e "${GREEN}======================================================================${NC}"
echo ""
