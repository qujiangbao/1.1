#!/bin/bash
# Industrial Park Agent v1.2 — Competition Warmup Script
# Run 10 minutes before demo to preheat LLM + DB connections

set -e
BASE="${1:-http://localhost:8000}"
API="$BASE/api/v1"

echo "=== Industrial Park Agent v1.2 — Pre-Demo Warmup ==="
echo "  base: $BASE"
echo ""

# 1. Health check
echo "[1/5] Health check..."
curl -sf "$API/health" | python3 -m json.tool 2>/dev/null || echo "  ⚠️ Health check failed"
echo ""

# 2. Login + get token
echo "[2/5] Login..."
TOKEN=$(curl -sf -X POST "$API/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
if [ -n "$TOKEN" ]; then
  echo "  ✅ Token obtained"
else
  echo "  ⚠️  No token (AUTH_ENABLED=false?)"
fi
echo ""

# 3. Agent status
echo "[3/5] Agent status..."
curl -sf "$API/agent/status" ${TOKEN:+-H "Authorization: Bearer $TOKEN"} \
  | python3 -m json.tool 2>/dev/null || echo "  ⚠️ Status check failed"
echo ""

# 4. Warmup: run a simple agent task
echo "[4/5] LLM Warmup — running simple agent task..."
START=$(date +%s)
curl -sf -X POST "$API/agent/chat" \
  -H "Content-Type: application/json" \
  ${TOKEN:+-H "Authorization: Bearer $TOKEN"} \
  -d '{"message":"分析广州机器人产业"}' \
  -o /dev/null --max-time 60 2>/dev/null
ELAPSED=$(($(date +%s) - START))
echo "  ✅ Warmup complete (${ELAPSED}s)"
echo ""

# 5. Compound task warmup
echo "[5/5] Full pipeline warmup — compound task..."
START=$(date +%s)
curl -sf -X POST "$API/agent/chat" \
  -H "Content-Type: application/json" \
  ${TOKEN:+-H "Authorization: Bearer $TOKEN"} \
  -d '{"message":"分析机器人产业链，推荐招商企业，评估风险并匹配政策"}' \
  -o /dev/null --max-time 120 2>/dev/null
ELAPSED=$(($(date +%s) - START))
echo "  ✅ Full pipeline warmup complete (${ELAPSED}s)"

echo ""
echo "=== Warmup Complete — Ready for Demo! ==="
