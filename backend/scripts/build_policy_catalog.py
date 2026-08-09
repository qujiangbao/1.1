#!/usr/bin/env python3
"""Build the fast, validated runtime catalog for one cleaned policy snapshot."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.tools.adapters.policy_crawl4ai import PolicyCrawl4AIData  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--snapshot",
        type=Path,
        required=True,
        help="Snapshot containing _clean_manifest.json and clean/",
    )
    args = parser.parse_args()

    adapter = PolicyCrawl4AIData(args.snapshot)
    payload = adapter.catalog_payload()
    target = adapter.data_dir / "_catalog.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    temporary.replace(target)
    print(f"Built policy catalog: {target} ({len(payload['documents'])} documents)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
