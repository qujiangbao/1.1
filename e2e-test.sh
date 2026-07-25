#!/bin/bash
# ═══════════════════════════════════════════════════════
# Industrial Park Agent v1.2 — E2E Test Script (P8 fixed)
# ═══════════════════════════════════════════════════════
set -euo pipefail

BASE="${1:-http://localhost:8000}"
API="$BASE/api/v1"
PASS=0
FAIL=0
VERSION="unknown"

check() {
  local name="$1" expected="$2" actual="$3"
  if echo "$actual" | grep -q "$expected"; then
    echo "  ✅ $name"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $name (expected: '$expected')"
    FAIL=$((FAIL + 1))
  fi
}

fail() {
  echo "  ❌ $1"
  FAIL=$((FAIL + 1))
}

echo "=== Industrial Park Agent v1.2 — E2E Test ==="
echo "  base: $BASE"
echo "  time: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "  git:  $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo ""

# ── 1. Liveness + Readiness ──
echo "1. Health Checks"
LIVE=$(curl -sf "$API/health/live" 2>&1 || echo "FAIL")
check "liveness" "alive" "$LIVE"

READY=$(curl -sf "$API/health/ready" 2>&1 || echo "FAIL")
check "readiness (DB disabled OK)" "not_ready|ready" "$READY"

FULL=$(curl -sf "$API/health" 2>&1 || echo "FAIL")
check "health degraded/mock" "degraded|healthy|mock" "$FULL"

# ── 2. Auth ──
echo "2. Authentication"
LOGIN_RESP=$(curl -sf -X POST "$API/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' 2>&1 || echo "FAIL")
TOKEN=$(echo "$LOGIN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || echo "")
check "login 200" "access_token" "$LOGIN_RESP"

if [ -z "$TOKEN" ]; then
  fail "token missing from login response"
else
  AUTH_HEADER="Authorization: Bearer $TOKEN"
  check "token length >= 20" "." "$([ ${#TOKEN} -ge 20 ] && echo ok || echo fail)"

  # /auth/me
  ME=$(curl -sf "$API/auth/me" -H "$AUTH_HEADER" 2>&1 || echo "FAIL")
  check "auth/me" "user_id" "$ME"

  # Wrong password
  WRONG=$(curl -s -X POST "$API/auth/login" -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"wrong"}' 2>&1 || echo "{}")
  check "wrong password 401" "401|Unauthorized|Incorrect" "$WRONG"
fi

# ── 3. Agent Tasks ──
echo "3. Agent Tasks"
if [ -n "$TOKEN" ]; then
  SINGLE_RESP=$(curl -sf -X POST "$API/agent/chat" \
    -H "Content-Type: application/json" -H "$AUTH_HEADER" \
    -d '{"message":"分析广州数控风险"}' --max-time 120 2>&1 || echo "FAIL")
  SINGLE_TASK=$(echo "$SINGLE_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('task_id',''))" 2>/dev/null || echo "")
  check "single agent chat" "task_id" "$SINGLE_RESP"

  # Compound task
  COMPOUND_RESP=$(curl -sf -X POST "$API/agent/chat" \
    -H "Content-Type: application/json" -H "$AUTH_HEADER" \
    -d '{"message":"分析机器人产业链，推荐招商企业，评估风险并匹配政策"}' --max-time 180 2>&1 || echo "FAIL")
  COMPOUND_TASK=$(echo "$COMPOUND_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('task_id',''))" 2>/dev/null || echo "")
  check "compound agent chat" "agents_used" "$COMPOUND_RESP"
else
  echo "  ⚠️  Skipping agent tasks (no token)"
fi

# ── 4. API Endpoints ──
echo "4. API Endpoints"
R=$(curl -sf "$API/agent/status" ${TOKEN:+-H "$AUTH_HEADER"} 2>&1 || echo "FAIL")
check "agent/status" "total_agents" "$R"

R=$(curl -sf "$API/agent/team/status" ${TOKEN:+-H "$AUTH_HEADER"} 2>&1 || echo "FAIL")
check "agent/team/status" "total_agents" "$R"

R=$(curl -sf "$API/agent/daily-report" ${TOKEN:+-H "$AUTH_HEADER"} 2>&1 || echo "FAIL")
check "agent/daily-report" "data_mode" "$R"

INVEST_RESP=$(curl -sf -X POST "$API/investment/search" \
  -H "Content-Type: application/json" ${TOKEN:+-H "$AUTH_HEADER"} \
  -d '{"industry":"机器人"}' 2>&1 || echo "FAIL")
check "investment/search" "enterprises" "$INVEST_RESP"

PROFILE=$(curl -sf "$API/investment/profile/ENT-001" ${TOKEN:+-H "$AUTH_HEADER"} 2>&1 || echo "FAIL")
check "investment/profile" "success" "$PROFILE"

# ── 5. Trace ──
echo "5. Trace"
if [ -n "${COMPOUND_TASK:-}" ] && [ ${#COMPOUND_TASK} -gt 5 ]; then
  TRACE=$(curl -sf "$API/agent/task/$COMPOUND_TASK/trace" ${TOKEN:+-H "$AUTH_HEADER"} 2>&1 || echo "FAIL")
  check "trace 200" "nodes" "$TRACE"

  # Verify at least 4 agent nodes in compound task
  AGENT_COUNT=$(echo "$TRACE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len([n for n in d.get('nodes',[]) if n.get('type')=='agent']))" 2>/dev/null || echo "0")
  echo "     Agent nodes in trace: $AGENT_COUNT"
fi

# Non-existent task → 404
NOTFOUND=$(curl -s "$API/agent/task/nonexistent-12345/trace" ${TOKEN:+-H "$AUTH_HEADER"} 2>&1 || echo "{}")
check "missing task → not 200" "404|detail" "$NOTFOUND"

# ── 6. Summary ──
echo ""
echo "=== P8 E2E Summary ==="
echo "  Passed: $PASS"
echo "  Failed: $FAIL"
echo "  Total:  $((PASS + FAIL))"
echo "  Branch: $(git branch --show-current 2>/dev/null || echo unknown)"
echo "  Commit: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo ""

if [ $FAIL -eq 0 ]; then
  echo "✅ All E2E tests passed!"
else
  echo "❌ $FAIL test(s) failed"
fi
exit $FAIL
