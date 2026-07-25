#!/bin/bash
# ═════════════════════════════════════════════════════
# Industrial Park Agent — WSL Bootstrap Script
# ═════════════════════════════════════════════════════
# Creates a self-contained virtual environment.
# Does NOT depend on external project .venv paths.
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3.12}"
VENV_DIR="${VENV_DIR:-.venv}"

echo "=== Industrial Park Agent — Bootstrap ==="

# 1. Check environment
if ! grep -qi "microsoft" /proc/version 2>/dev/null && ! uname -r | grep -qi "microsoft"; then
    echo "  ⚠️  Not running in WSL. Continuing anyway..."
fi

# 2. Check Python version
PY_VER=$("$PYTHON_BIN" --version 2>&1 | grep -oP '\d+\.\d+')
echo "  Python: $PY_VER"

# 3. Check uv
if ! command -v uv &>/dev/null; then
    echo "  ❌ uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# 4. Create venv
if [ ! -d "$VENV_DIR/bin" ]; then
    echo "  Creating venv: $VENV_DIR"
    uv venv --python "$PYTHON_BIN" "$VENV_DIR"
else
    echo "  Venv exists: $VENV_DIR"
fi

# 5. Install deps
echo "  Installing dependencies..."
uv pip install -r requirements.txt --python "$VENV_DIR/bin/python3"
uv pip install -r requirements-dev.txt --python "$VENV_DIR/bin/python3"

echo ""
echo "  ✅ Bootstrap complete!"
echo "  Activate: source $VENV_DIR/bin/activate"
echo "  Run:      .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo "  Test:     PYTHONPATH=. .venv/bin/python3 -m pytest tests/ -q"
