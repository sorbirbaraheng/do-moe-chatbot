#!/usr/bin/env bash
set -euo pipefail

# Rate-safe live smoke run (defaults can be overridden via env or args)
BASE_URL="${BASE_URL:-http://localhost:5001}"
INTERVAL="${INTERVAL:-8}"
MAX_CASES="${MAX_CASES:-6}"
RETRIES="${RETRIES:-1}"
CATEGORY="${CATEGORY:-school}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

python3 "${ROOT_DIR}/scripts/run_live_smoke_safe.py" \
  --base-url "${BASE_URL}" \
  --interval "${INTERVAL}" \
  --max-cases "${MAX_CASES}" \
  --retries "${RETRIES}" \
  --stop-on-429 \
  --category "${CATEGORY}" \
  "$@"
