"""Orchestrate governed policy crawl runs and downstream indexing."""
from __future__ import annotations

import asyncio
from datetime import datetime
import json
from pathlib import Path

from app.config import get_settings


def _resolve_backend_path(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (Path.cwd() / path).resolve()


async def execute_policy_crawl_run(run_id: str) -> None:
    from app.database.models.policy_crawler import PolicyCrawlRun
    from app.database.session import SessionLocal

    if SessionLocal is None:
        return
    async with SessionLocal() as session:
        run = await session.get(PolicyCrawlRun, run_id)
        if run is None or run.status != "QUEUED":
            return
        run.status = "RUNNING"
        run.started_at = datetime.utcnow()
        await session.commit()
        pages, workers, force = run.pages, run.workers, run.force

    settings = get_settings()
    output = _resolve_backend_path(settings.policy_crawl_data_dir)
    config = _resolve_backend_path(settings.policy_crawler_source_config)
    stats: dict = {}
    error: str | None = None
    final_status = "SUCCEEDED"
    try:
        from app.services.policy_crawler_engine import PolicyCrawlerEngine

        engine = PolicyCrawlerEngine(
            config_path=config,
            output_path=output,
            crawl4ai_api=settings.policy_crawler_api_url,
            crawl4ai_token=settings.policy_crawler_api_token,
            refresh_days=settings.policy_crawler_refresh_days,
        )
        stats = await asyncio.to_thread(
            engine.refresh,
            pages=pages,
            workers=workers,
            force=force,
        )

        # Publish the catalog after the crawler index is atomically replaced.
        from app.tools.adapters.policy_crawl4ai import PolicyCrawl4AIData

        catalog_payload = PolicyCrawl4AIData(output).catalog_payload()
        catalog_tmp = output / "_catalog.json.tmp"
        catalog_tmp.write_text(
            json.dumps(catalog_payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        catalog_tmp.replace(output / "_catalog.json")
        stats["catalog_documents"] = len(catalog_payload.get("documents", []))

        # Keep the database and pgvector store in the same run audit.  A cache
        # refresh remains useful if embedding temporarily fails, hence PARTIAL.
        try:
            from app.services.policy_ingestion import PolicyIngestionService

            ingestion = await PolicyIngestionService(
                provider=settings.policy_embedding_provider,
                model=settings.policy_embedding_model,
                dimensions=settings.policy_embedding_dimensions,
            ).ingest_cache(output, continue_on_error=True)
            stats["ingestion"] = ingestion.to_dict()
            if ingestion.failed:
                final_status = "PARTIAL"
                error = f"{ingestion.failed}份政策的向量入库失败，缓存已更新"
        except Exception as exc:
            final_status = "PARTIAL"
            error = f"政策缓存已更新，但数据库/向量同步失败: {exc}"
    except Exception as exc:
        final_status = "FAILED"
        error = str(exc)

    async with SessionLocal() as session:
        run = await session.get(PolicyCrawlRun, run_id)
        if run is None:
            return
        run.status = final_status
        run.stats = stats
        run.error = error
        run.finished_at = datetime.utcnow()
        await session.commit()
