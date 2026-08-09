#!/usr/bin/env bash
# Industrial Park Agent v1.3 — HTTP/JSON E2E checks
set -uo pipefail

BASE="${1:-http://localhost:8000}"
API="$BASE/api/v1"
PASS=0
FAIL=0
HTTP_STATUS=""
HTTP_BODY=""

request() {
  local response
  response=$(curl --noproxy '*' -sS -w $'\n%{http_code}' "$@" 2>&1)
  local curl_status=$?
  if [ "$curl_status" -ne 0 ]; then
    HTTP_STATUS="000"
    HTTP_BODY="$response"
    return
  fi
  HTTP_STATUS="${response##*$'\n'}"
  HTTP_BODY="${response%$'\n'*}"
}

pass() {
  echo "  ✓ $1"
  PASS=$((PASS + 1))
}

fail() {
  echo "  ✗ $1"
  FAIL=$((FAIL + 1))
}

check_status() {
  local name="$1" expected="$2"
  if [ "$HTTP_STATUS" = "$expected" ]; then
    pass "$name"
  else
    fail "$name (expected HTTP $expected, got $HTTP_STATUS)"
  fi
}

check_status_one_of() {
  local name="$1"
  shift
  local expected
  for expected in "$@"; do
    if [ "$HTTP_STATUS" = "$expected" ]; then
      pass "$name"
      return
    fi
  done
  fail "$name (unexpected HTTP $HTTP_STATUS)"
}

check_json() {
  local name="$1" expression="$2"
  if printf '%s' "$HTTP_BODY" | python3 -c \
    "import json,sys; data=json.load(sys.stdin); assert ($expression)" 2>/dev/null; then
    pass "$name"
  else
    fail "$name (invalid JSON or assertion failed)"
  fi
}

echo "=== Industrial Park Agent v1.3 E2E ==="
echo "  base: $BASE"
echo "  time: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "  git:  $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo

echo "1. Health Checks"
request "$API/health/live"
check_status "liveness status" "200"
check_json "liveness body" "data.get('status') == 'alive'"

request "$API/health/ready"
check_status_one_of "readiness returns a defined state" "200" "503"
check_json "readiness body" "data.get('status') in ('ready', 'not_ready')"

request "$API/health"
check_status "health status" "200"
check_json "health body" "data.get('status') in ('healthy', 'degraded')"

echo "2. Authentication"
request -X POST "$API/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'
check_status "login status" "200"
check_json "login token field" "isinstance(data.get('access_token'), str) and len(data['access_token']) >= 20"
TOKEN=$(printf '%s' "$HTTP_BODY" | python3 -c \
  "import json,sys; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)

AUTH_ARGS=()
if [ -n "$TOKEN" ]; then
  AUTH_ARGS=(-H "Authorization: Bearer $TOKEN")
  request "$API/auth/me" "${AUTH_ARGS[@]}"
  check_status "auth/me status" "200"
  check_json "auth/me body" "'user_id' in data"
else
  fail "token missing from login response"
fi

request -X POST "$API/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"wrong"}'
check_status "wrong password status" "401"

echo "3. Agent Tasks"
COMPOUND_TASK=""
if [ -n "$TOKEN" ]; then
  request -X POST "$API/agent/chat" \
    -H "Content-Type: application/json" "${AUTH_ARGS[@]}" \
    -d '{"message":"分析机器人产业链，推荐招商企业，评估风险并匹配政策"}' \
    --max-time 180
  check_status "compound agent chat status" "200"
  check_json "compound agent chat body" \
    "isinstance(data.get('task_id'), str) and len(data.get('agents_used', [])) >= 4"
  COMPOUND_TASK=$(printf '%s' "$HTTP_BODY" | python3 -c \
    "import json,sys; print(json.load(sys.stdin).get('task_id',''))" 2>/dev/null)
else
  fail "compound agent chat skipped because login failed"
fi

echo "4. API Endpoints"
request "$API/agent/status" "${AUTH_ARGS[@]}"
check_status "agent/status status" "200"
check_json "agent/status body" "data.get('total_agents', 0) >= 6"

request "$API/agent/team/status" "${AUTH_ARGS[@]}"
check_status "agent/team/status status" "200"
check_json "agent/team/status body" "data.get('data', {}).get('total_agents', 0) >= 6"

request "$API/agent/daily-report" "${AUTH_ARGS[@]}"
check_status "agent/daily-report status" "200"
check_json "agent/daily-report body" "'data_mode' in data.get('data', {})"

request -X POST "$API/investment/search" \
  -H "Content-Type: application/json" "${AUTH_ARGS[@]}" \
  -d '{"industry":"机器人"}'
check_status "investment/search status" "200"
check_json "investment/search body" \
  "len(data.get('data', {}).get('enterprises', [])) >= 1 and data['data']['total'] == len(data['data']['enterprises'])"

request -X POST "$API/policy/search" \
  -H "Content-Type: application/json" "${AUTH_ARGS[@]}" \
  -d '{"query":"机器人产业扶持","top_k":3}'
check_status "policy/search status" "200"
check_json "policy/search source evidence" \
  "data.get('data', {}).get('chunks') and all(item.get('metadata', {}).get('source_url', '').startswith('https://www.gz.gov.cn/') for item in data['data']['chunks'])"

request "$API/investment/profile/ENT-001" "${AUTH_ARGS[@]}"
check_status "investment/profile status" "200"
check_json "investment/profile body" "data.get('success') is True"

echo "5. Trace"
if [ -n "$COMPOUND_TASK" ]; then
  request "$API/agent/task/$COMPOUND_TASK/trace" "${AUTH_ARGS[@]}"
  check_status "trace status" "200"
  check_json "trace body" "len(data.get('nodes', [])) >= 5"
else
  fail "trace skipped because compound task was not created"
fi

request "$API/agent/task/nonexistent-12345/trace" "${AUTH_ARGS[@]}"
check_status "missing trace status" "404"
check_json "missing trace body" "data.get('detail') == 'Task not found or trace not yet generated'"

echo
echo "=== E2E Summary ==="
echo "  Passed: $PASS"
echo "  Failed: $FAIL"
echo "  Total:  $((PASS + FAIL))"
echo "  Branch: $(git branch --show-current 2>/dev/null || echo unknown)"
echo "  Commit: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"

if [ "$FAIL" -eq 0 ]; then
  echo "✓ All E2E tests passed"
else
  echo "✗ $FAIL test(s) failed"
fi
exit "$FAIL"
