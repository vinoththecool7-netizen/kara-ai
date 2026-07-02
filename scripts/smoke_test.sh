#!/usr/bin/env bash
# smoke_test.sh — Validates that `docker compose up` starts the full Kara stack
# and that core API endpoints respond correctly.
#
# Usage (from project root):
#   chmod +x scripts/smoke_test.sh
#   ./scripts/smoke_test.sh
#
# Uses docker-compose.test.yml override so LLM_PROVIDER=fake — no API key needed.

set -euo pipefail

# ---------------------------------------------------------------------------
# Colors and helpers
# ---------------------------------------------------------------------------
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS=0
FAIL=0

pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    PASS=$((PASS + 1))
}

fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    FAIL=$((FAIL + 1))
}

info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

# ---------------------------------------------------------------------------
# Pre-flight: verify required tools are available
# ---------------------------------------------------------------------------
info "Checking required tools..."

if ! command -v docker &>/dev/null; then
    echo -e "${RED}[ERROR]${NC} 'docker' not found. Please install Docker." >&2
    exit 1
fi

if ! docker compose version &>/dev/null; then
    echo -e "${RED}[ERROR]${NC} 'docker compose' (v2 plugin) not found." >&2
    exit 1
fi

if ! command -v curl &>/dev/null; then
    echo -e "${RED}[ERROR]${NC} 'curl' not found. Please install curl." >&2
    exit 1
fi

info "All required tools found."

# ---------------------------------------------------------------------------
# Ensure the script runs from the project root
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"
info "Working directory: ${PROJECT_ROOT}"

# ---------------------------------------------------------------------------
# Cleanup trap — always bring the stack down on exit (pass or fail)
# ---------------------------------------------------------------------------
cleanup() {
    info "Tearing down stack (docker compose down -v)..."
    docker compose -f docker-compose.yml -f docker-compose.test.yml down -v --remove-orphans 2>/dev/null || true
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Build and start the stack
# ---------------------------------------------------------------------------
info "Building and starting the stack..."
# Only db + api are needed for the API smoke test (web build is slow)
docker compose -f docker-compose.yml -f docker-compose.test.yml up -d --build db api

# ---------------------------------------------------------------------------
# Wait for the API to become healthy (max 60 s, polling every 2 s)
# ---------------------------------------------------------------------------
API_URL="http://localhost:8000"
MAX_WAIT=120
INTERVAL=2
ELAPSED=0

info "Waiting for API to be ready at ${API_URL}/health (max ${MAX_WAIT}s)..."

until curl -sf "${API_URL}/health" -o /dev/null; do
    if [ "${ELAPSED}" -ge "${MAX_WAIT}" ]; then
        echo -e "${RED}[ERROR]${NC} API did not become ready within ${MAX_WAIT}s." >&2
        exit 1
    fi
    sleep "${INTERVAL}"
    ELAPSED=$((ELAPSED + INTERVAL))
done

info "API is ready (${ELAPSED}s elapsed)."

# ---------------------------------------------------------------------------
# Test 1 — Health endpoint
# ---------------------------------------------------------------------------
info "Running Test 1: GET /health"
HEALTH_RESPONSE="$(curl -s --max-time 30 "${API_URL}/health" || true)"

if echo "${HEALTH_RESPONSE}" | grep -q '"status"'; then
    pass "Test 1 — Health endpoint returns JSON with 'status' key"
else
    fail "Test 1 — Health endpoint response did not contain 'status'. Got: ${HEALTH_RESPONSE}"
fi

# ---------------------------------------------------------------------------
# Test 2 — Chat JSON endpoint
# ---------------------------------------------------------------------------
info "Running Test 2: POST /api/v1/chat (Accept: application/json)"
CHAT_JSON_RESPONSE="$(curl -s --max-time 30 \
    -X POST "${API_URL}/api/v1/chat" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json" \
    -d '{"message":"Hello"}' || true)"

if echo "${CHAT_JSON_RESPONSE}" | grep -q '"session_id"'; then
    pass "Test 2 — Chat JSON endpoint returns JSON with 'session_id' key"
else
    fail "Test 2 — Chat JSON response did not contain 'session_id'. Got: ${CHAT_JSON_RESPONSE}"
fi

# ---------------------------------------------------------------------------
# Test 3 — Chat SSE endpoint
# ---------------------------------------------------------------------------
info "Running Test 3: POST /api/v1/chat (SSE — default Accept)"
CHAT_SSE_RESPONSE="$(curl -s --max-time 30 \
    -X POST "${API_URL}/api/v1/chat" \
    -H "Content-Type: application/json" \
    -d '{"message":"Hi"}' || true)"

if echo "${CHAT_SSE_RESPONSE}" | grep -q "data:"; then
    pass "Test 3 — Chat SSE endpoint returns SSE stream with 'data:' lines"
else
    fail "Test 3 — Chat SSE response did not contain 'data:'. Got: ${CHAT_SSE_RESPONSE}"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "------------------------------------------------------------"
TOTAL=$((PASS + FAIL))
echo -e "Results: ${GREEN}${PASS}/${TOTAL} passed${NC}  ${RED}${FAIL} failed${NC}"
echo "------------------------------------------------------------"

if [ "${FAIL}" -gt 0 ]; then
    exit 1
fi

exit 0
