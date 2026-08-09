#!/usr/bin/env python3
"""Incrementally import the validated Crawl4AI policy cache into pgvector."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--provider", choices=("openai", "dashscope", "mock"))
    parser.add_argument("--model")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


async def run(args: argparse.Namespace) -> int:
    from app.config import get_settings
    from app.tools.adapters.policy_crawl4ai import PolicyCrawl4AIData

    settings = get_settings()
    cache = args.cache or Path(settings.policy_crawl_data_dir)
    adapter = PolicyCrawl4AIData(cache)
    if args.dry_run:
        print(json.dumps(adapter.stats(), ensure_ascii=False, indent=2))
        return 0

    provider = args.provider or settings.policy_embedding_provider
    model = args.model or settings.policy_embedding_model
    if settings.app_env.lower() == "production" and provider == "mock":
        raise ValueError("Mock embeddings are forbidden in production")

    from app.database.session import close_db, init_db
    from app.services.policy_ingestion import PolicyIngestionService

    await init_db(settings.database_url)
    try:
        service = PolicyIngestionService(
            provider=provider,
            model=model,
            dimensions=settings.policy_embedding_dimensions,
        )
        report = await service.ingest_cache(
            cache,
            force=args.force,
            continue_on_error=args.continue_on_error,
        )
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return 1 if report.failed else 0
    finally:
        await close_db()


def main() -> int:
    return asyncio.run(run(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
