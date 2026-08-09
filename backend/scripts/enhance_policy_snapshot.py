#!/usr/bin/env python3
"""Run offline Docling enhancement for one explicit policy snapshot."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.policy_document_enhancement import (  # noqa: E402
    DEFAULT_WORKER_PYTHON,
    DEFAULT_WORKER_SCRIPT,
    PolicyDocumentEnhancer,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--snapshot",
        type=Path,
        required=True,
        help="Complete snapshot containing raw/clean manifests and attachments",
    )
    parser.add_argument(
        "--worker-python",
        type=Path,
        default=DEFAULT_WORKER_PYTHON,
    )
    parser.add_argument(
        "--worker-script",
        type=Path,
        default=DEFAULT_WORKER_SCRIPT,
    )
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--run-id")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    enhancer = PolicyDocumentEnhancer(
        args.snapshot,
        worker_python=args.worker_python,
        worker_script=args.worker_script,
        timeout_seconds=args.timeout,
        run_id=args.run_id,
        force=args.force,
    )
    summary = enhancer.run()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
