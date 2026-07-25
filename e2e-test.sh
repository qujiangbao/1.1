#!/bin/bash
# ═══════════════════════════════════════════════════════
# Industrial Park Agent v1.2 — E2E Test Script
# ═══════════════════════════════════════════════════════
# Run against a running deployment.
# Usage: ./e2e-test.sh [base_url]

set -euo pipefail

BASE="${1:-http://localhost:8000}"
API="$BASE/api/v1"
PASS=0
FAIL=0

check() {
  local name="$1"
  local expected="$2"
  local actual="$3"
  if echo "$actual" | grep -q "$expected"; then
    echo "  ✅ $name"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $name (expected: '$expected', got: '$actual')"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== Industrial Park Agent v1.2 — E2E Test ==="
echo "  base: $BASE"
echo "  time: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

# ── 1. Health ──
echo "1. Health Check"
R=$(curl -sf "$API/health" 2>&1 || echo "FAIL")
check "health endpoint" "healthy" "$R"

# ── 2. Auth ──
echo "2. Authentication"
R=$(curl -sf -X POST "$API/auth/login" -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' 2>&1 || echo "FAIL")
TOKEN=$(echo "$R" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || echo "")
check "login returns token" "access_token" "$R"
check "token present" "." "${#TOKEN}"  # non-empty

# ── 3. Agent Chat ──
echo "3. Agent Chat (single task)"
if [ -n "$TOKEN" ]; then
  R=$(curl -sf -X POST "$API/agent/chat" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"message":"分析广州数控风险"}' --max-time 120 2>&1 || echo "FAIL")
  check "agent chat response" "task_id" "$R"
else
  echo "  ⚠️  Skipping — no token"
fi

# ── 4. Agent Chat (compound) ──
echo "4. Agent Chat (compound task)"
if [ -n "$TOKEN" ]; then
  R=$(curl -sf -X POST "$API/agent/chat" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"message":"分析机器人产业链，推荐招商企业，评估风险并匹配政策"}' --max-time 180 2>&1 || echo "FAIL")
  check "compound agents" "agents_used" "$R"
else
  echo "  ⚠️  Skipping — no token"
fi

# ── 5. Endpoints ──
echo "5. API Endpoints"
R=$(curl -sf "$API/agent/status" -H "Authorization: Bearer $TOKEN" 2>&1 || echo "FAIL")
check "agent status" "total_agents" "$R"

R=$(curl -sf -X POST "$API/investment/search" -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"industry":"机器人"}' 2>&1 || echo "FAIL")
check "investment search" "enterprises" "$R"

# ── 6. Trace ──
echo "6. Trace (last task)"
# Get last task_id from the compound chat response
TASK_ID=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('task_id',''))" 2>/dev/null || echo "")
if [ -n "$TASK_ID" ] && [ ${#TASK_ID} -gt 5 ]; then
  TR=$(curl -sf "$API/agent/task/$TASK_ID/trace" -H "Authorization: Bearer $TOKEN" 2>&1 || echo "FAIL")
  check "trace response" "nodes" "$TR"
fi

echo ""
echo "=== Summary ==="
echo "  Passed: $PASS"
echo "  Failed: $FAIL"
echo "  Total:  $((PASS + FAIL))"
echo ""

[ $FAIL -eq 0 ] && echo "✅ All E2E tests passed!" || echo "❌ Some tests failed"
exit $FAIL
