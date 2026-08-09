"""Incrementally ingest validated Crawl4AI policy cache into PostgreSQL."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
import hashlib
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.database.models.business import (
    Policy,
    PolicyChunk,
    PolicyDocument,
)
from app.services.chunker import TextChunker
from app.services.embedding import EmbeddingService
from app.services.metadata_extractor import MetadataExtractor, PolicyMetadata
from app.services.vector_store import VectorStore
from app.tools.adapters.policy_crawl4ai import CrawledPolicy, PolicyCrawl4AIData


@dataclass
class IngestionReport:
    total_documents: int = 0
    inserted_or_updated: int = 0
    unchanged: int = 0
    failed: int = 0
    chunks_written: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    normalized = value.strip().replace("年", "-").replace("月", "-").replace("日", "")
    try:
        return date.fromisoformat(normalized)
    except ValueError:
        return None


def _metadata(document: CrawledPolicy) -> PolicyMetadata:
    extracted = MetadataExtractor().extract(document.content)
    extracted.title = document.title
    extracted.department = document.department or extracted.department
    extracted.level = "municipal"
    extracted.region_scope = ["广州市"]
    extracted.publish_date = document.publish_date or extracted.publish_date
    extracted.expire_date = document.expire_date or None
    return extracted


def _chunk_provenance(
    document: CrawledPolicy, provider: str, model: str
) -> dict[str, str]:
    return {
        "source_url": document.source_url,
        "document_number": document.document_number,
        "parser": document.parser,
        "parser_version": document.parser_version,
        "parse_status": document.parse_status,
        "input_sha256": document.input_sha256,
        "selected_artifact": document.selected_artifact,
        "embedding_provider": provider,
        "embedding_model": model,
    }


class PolicyIngestionService:
    def __init__(
        self,
        provider: str,
        model: str,
        dimensions: int = 1536,
    ) -> None:
        self.provider = provider
        self.model = model
        self.dimensions = dimensions
        self.embedder = EmbeddingService(provider, model, dimensions)
        self.chunker = TextChunker(chunk_size=512, overlap=50)
        self.vector_store = VectorStore()

    async def ingest_cache(
        self,
        data_dir: str | Path | None = None,
        *,
        force: bool = False,
        continue_on_error: bool = False,
    ) -> IngestionReport:
        adapter = PolicyCrawl4AIData(data_dir)
        documents = adapter.documents()
        report = IngestionReport(total_documents=len(documents))

        for document in documents:
            try:
                changed, chunk_count = await self._ingest_document(
                    document,
                    force=force,
                )
            except Exception:
                report.failed += 1
                if not continue_on_error:
                    raise
                continue
            if changed:
                report.inserted_or_updated += 1
                report.chunks_written += chunk_count
            else:
                report.unchanged += 1
        return report

    async def _ingest_document(
        self,
        document: CrawledPolicy,
        *,
        force: bool,
    ) -> tuple[bool, int]:
        from app.database.session import SessionLocal

        if SessionLocal is None:
            raise RuntimeError("Database is not initialized")

        content_hash = document.content_hash or hashlib.sha256(
            document.content.encode("utf-8")
        ).hexdigest()
        filename = document.filename or f"{document.policy_id}.md"
        metadata = _metadata(document)

        async with SessionLocal() as session:
            policy_statement = (
                insert(Policy)
                .values(
                    policy_id=document.policy_id,
                    title=document.title,
                    level="municipal",
                    department=document.department,
                    category=metadata.category,
                    industry_scope=metadata.industry_scope,
                    region_scope=["广州市"],
                    content=document.content,
                    publish_date=_parse_date(
                        document.publish_date or metadata.publish_date or ""
                    ),
                    expire_date=_parse_date(document.expire_date),
                    status=(
                        "active"
                        if document.status in ("", "有效", "现行有效")
                        else "inactive"
                    ),
                    source=document.source_url,
                )
                .on_conflict_do_update(
                    index_elements=[Policy.policy_id],
                    set_={
                        "title": document.title,
                        "level": "municipal",
                        "department": document.department,
                        "category": metadata.category,
                        "industry_scope": metadata.industry_scope,
                        "region_scope": ["广州市"],
                        "content": document.content,
                        "publish_date": _parse_date(
                            document.publish_date or metadata.publish_date or ""
                        ),
                        "expire_date": _parse_date(document.expire_date),
                        "status": (
                            "active"
                            if document.status in ("", "有效", "现行有效")
                            else "inactive"
                        ),
                        "source": document.source_url,
                    },
                )
            )
            await session.execute(policy_statement)

            existing = (
                await session.execute(
                    select(PolicyDocument)
                    .where(
                        PolicyDocument.policy_id == document.policy_id,
                        PolicyDocument.filename == filename,
                    )
                    .order_by(PolicyDocument.id.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()

            if existing is None:
                existing = PolicyDocument(
                    policy_id=document.policy_id,
                    filename=filename,
                    file_format="md",
                )
                session.add(existing)
                await session.flush()

            content_changed = bool(
                existing.file_hash and existing.file_hash != content_hash
            )
            if content_changed:
                policy = await session.get(Policy, document.policy_id)
                if policy is not None and policy.eligibility_conditions:
                    # A reviewed rule is only valid for the exact source text
                    # that was reviewed.  Preserve the extraction for audit,
                    # but force every rule back through human review.
                    policy.eligibility_conditions = [
                        {**condition, "review_status": "DRAFT"}
                        for condition in policy.eligibility_conditions
                    ]
                    policy.conditions_reviewed_at = None
                    policy.conditions_reviewed_by = None

            chunk_count = int(
                (
                    await session.execute(
                        select(func.count(PolicyChunk.id)).where(
                            PolicyChunk.policy_id == document.policy_id
                        )
                    )
                ).scalar()
                or 0
            )
            stored_chunk_metadata = (
                await session.execute(
                    select(PolicyChunk.metadata_)
                    .where(PolicyChunk.policy_id == document.policy_id)
                    .limit(1)
                )
            ).scalar_one_or_none() or {}
            embedding_matches = (
                stored_chunk_metadata.get("embedding_provider") == self.provider
                and stored_chunk_metadata.get("embedding_model") == self.model
            )
            if (
                not force
                and existing.file_hash == content_hash
                and existing.parse_status == "indexed"
                and chunk_count > 0
                and embedding_matches
            ):
                await session.commit()
                return False, 0

            existing.file_hash = content_hash
            existing.file_size = document.file_size or len(
                document.content.encode("utf-8")
            )
            existing.page_count = 1
            existing.raw_text = document.content
            existing.parse_status = "parsed"
            existing.parse_error = None
            existing.updated_at = datetime.utcnow()
            await session.commit()
            document_id = existing.id

        chunks = self.chunker.chunk(
            document.content,
            metadata,
            policy_id=document.policy_id,
        )
        for chunk in chunks:
            chunk.document_id = document_id
            chunk.metadata.update(
                _chunk_provenance(document, self.provider, self.model)
            )
        if not chunks:
            await self._mark_document_failed(document_id, "Policy produced no chunks")
            raise ValueError(f"Policy produced no chunks: {document.policy_id}")

        try:
            embeddings = await self.embedder.embed_batch(
                [chunk.content for chunk in chunks]
            )
            written = await self.vector_store.replace_policy_chunks(
                document.policy_id,
                chunks,
                embeddings,
            )
        except Exception as exc:
            await self._mark_document_failed(document_id, str(exc))
            raise

        async with SessionLocal() as session:
            stored = await session.get(PolicyDocument, document_id)
            if stored is not None:
                stored.parse_status = "indexed"
                stored.parse_error = None
                stored.updated_at = datetime.utcnow()
                await session.commit()
        return True, written

    @staticmethod
    async def _mark_document_failed(document_id: int, error: str) -> None:
        from app.database.session import SessionLocal

        if SessionLocal is None:
            return
        async with SessionLocal() as session:
            stored = await session.get(PolicyDocument, document_id)
            if stored is not None:
                stored.parse_status = "failed"
                stored.parse_error = error[:2000]
                stored.updated_at = datetime.utcnow()
                await session.commit()
