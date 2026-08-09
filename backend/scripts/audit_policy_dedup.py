#!/usr/bin/env python3
"""Read-only audit of crawler deduplication against the current policy cache."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings  # noqa: E402
from app.services.policy_crawler_engine import (  # noqa: E402
    PolicyCrawlerEngine,
    deduplicate_entries,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path)
    args = parser.parse_args()
    settings = get_settings()
    cache = args.cache or Path(settings.policy_crawl_data_dir)
    engine = PolicyCrawlerEngine(
        config_path=settings.policy_crawler_source_config,
        output_path=cache,
    )
    entries = list(engine._load_index().values())
    classified, stats = deduplicate_entries(entries, engine.output)
    print(json.dumps({
        "input_documents": len(entries),
        "stats": stats,
        "duplicates": [
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "duplicate_of": item.get("duplicate_of"),
                "document_number": item.get("document_number"),
            }
            for item in classified
            if item.get("included", True) is False
        ],
        "versions": [
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "related_version_of": item.get("related_version_of"),
                "document_number": item.get("document_number"),
            }
            for item in classified
            if item.get("related_version_of")
        ],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
