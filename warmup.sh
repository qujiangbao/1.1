#!/usr/bin/env bash
# Warm the local backend before a demo without hiding readiness failures.
set -euo pipefail

BASE="${1:-http://localhost:8000}"
API="$BASE/api/v1"
MAX_ATTEMPTS="${WARMUP_MAX_ATTEMPTS:-30}"

echo "Waiting for backend liveness at $API/health/live"
for ((attempt = 1; attempt <= MAX_ATTEMPTS; attempt++)); do
  status=$(curl --noproxy '*' -sS -o /dev/null -w '%{http_code}' "$API/health/live" || true)
  if [ "$status" = "200" ]; then
    break
  fi
  if [ "$attempt" -eq "$MAX_ATTEMPTS" ]; then
    echo "Backend did not become live after $MAX_ATTEMPTS attempts" >&2
    exit 1
  fi
  sleep 2
done

curl --noproxy '*' -sS "$API/health/warmup"
echo
curl --noproxy '*' -sS -X POST "$API/policy/search" \
  -H 'Content-Type: application/json' \
  -d '{"query":"机器人产业扶持","top_k":3}' >/dev/null
echo "Warmup requests completed"
