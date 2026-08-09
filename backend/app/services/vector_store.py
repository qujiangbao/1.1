"""Typed pgvector read/write operations for policy chunks."""
from __future__ import annotations

import logging
from typing import List

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from app.database.models.business import PolicyChunk
from app.services.chunker import ChunkData

logger = logging.getLogger(__name__)


class VectorStore:
    """Persist policy chunks and embeddings through SQLAlchemy typed binds."""

    @staticmethod
    def _validate(
        chunks: List[ChunkData], embeddings: List[List[float]]
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("Chunk and embedding counts must match")
        for embedding in embeddings:
            if len(embedding) != 1536:
                raise ValueError(
                    f"Policy embedding dimension must be 1536, got {len(embedding)}"
                )

    async def upsert_chunks(
        self, chunks: List[ChunkData], embeddings: List[List[float]]
    ) -> int:
        """UPSERT chunks without deleting other chunks for the same policy."""
        if not chunks:
            return 0
        self._validate(chunks, embeddings)

        from app.database.session import SessionLocal
        if SessionLocal is None:
            raise RuntimeError("Database is not initialized")

        async with SessionLocal() as session:
            for chunk, embedding in zip(chunks, embeddings):
                statement = (
                    insert(PolicyChunk)
                    .values(
                        chunk_id=chunk.chunk_id,
                        policy_id=chunk.policy_id,
                        document_id=chunk.document_id,
                        chunk_index=chunk.chunk_index,
                        content=chunk.content,
                        content_hash=chunk.content_hash,
                        token_count=chunk.token_count,
                        embedding=embedding,
                        metadata_=chunk.metadata,
                    )
                    .on_conflict_do_update(
                        index_elements=[PolicyChunk.chunk_id],
                        set_={
                            "document_id": chunk.document_id,
                            "chunk_index": chunk.chunk_index,
                            "content": chunk.content,
                            "content_hash": chunk.content_hash,
                            "token_count": chunk.token_count,
                            "embedding": embedding,
                            "metadata": chunk.metadata,
                        },
                    )
                )
                await session.execute(statement)
            await session.commit()
        logger.info("VectorStore: upserted %d chunks", len(chunks))
        return len(chunks)

    async def replace_policy_chunks(
        self,
        policy_id: str,
        chunks: List[ChunkData],
        embeddings: List[List[float]],
    ) -> int:
        """Atomically replace all chunks for one changed policy."""
        self._validate(chunks, embeddings)
        if any(chunk.policy_id != policy_id for chunk in chunks):
            raise ValueError("Every replacement chunk must belong to the policy")

        from app.database.session import SessionLocal
        if SessionLocal is None:
            raise RuntimeError("Database is not initialized")

        async with SessionLocal() as session:
            await session.execute(
                delete(PolicyChunk).where(PolicyChunk.policy_id == policy_id)
            )
            for chunk, embedding in zip(chunks, embeddings):
                await session.execute(
                    insert(PolicyChunk).values(
                        chunk_id=chunk.chunk_id,
                        policy_id=chunk.policy_id,
                        document_id=chunk.document_id,
                        chunk_index=chunk.chunk_index,
                        content=chunk.content,
                        content_hash=chunk.content_hash,
                        token_count=chunk.token_count,
                        embedding=embedding,
                        metadata_=chunk.metadata,
                    )
                )
            await session.commit()
        logger.info(
            "VectorStore: replaced policy %s with %d chunks",
            policy_id,
            len(chunks),
        )
        return len(chunks)

    async def delete_policy_chunks(self, policy_id: str) -> int:
        from app.database.session import SessionLocal
        if SessionLocal is None:
            raise RuntimeError("Database is not initialized")
        async with SessionLocal() as session:
            result = await session.execute(
                delete(PolicyChunk).where(PolicyChunk.policy_id == policy_id)
            )
            await session.commit()
            return result.rowcount or 0

    async def count_chunks(self) -> int:
        from app.database.session import SessionLocal
        if SessionLocal is None:
            return 0
        async with SessionLocal() as session:
            result = await session.execute(select(func.count(PolicyChunk.id)))
            return int(result.scalar() or 0)

    async def ensure_index(self) -> None:
        """The Alembic migration owns index creation; verify it exists."""
        from app.database.session import SessionLocal
        if SessionLocal is None:
            raise RuntimeError("Database is not initialized")
        from sqlalchemy import text
        async with SessionLocal() as session:
            result = await session.execute(
                text(
                    """
                    SELECT 1
                    FROM pg_indexes
                    WHERE schemaname = current_schema()
                      AND indexname = 'idx_policy_chunks_embedding_hnsw'
                    """
                )
            )
            if result.scalar_one_or_none() != 1:
                raise RuntimeError(
                    "Policy vector index is missing; run Alembic migrations"
                )
