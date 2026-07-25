#!/bin/bash
# Acceptance test runner
cd "$(dirname "$0")/.."
echo "=== Industrial Park Agent — Acceptance Tests ==="
PYTHONPATH=. .venv/bin/python3 -m pytest tests/acceptance/ -v "$@"
