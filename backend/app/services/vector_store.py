"""VectorStore — pgvector 读写操作"""
from __future__ import annotations

import logging
from typing import List
from app.services.chunker import ChunkData

logger = logging.getLogger(__name__)


class VectorStore:
    """pgvector 向量存储"""

    async def upsert_chunks(
        self, chunks: List[ChunkData], embeddings: List[List[float]]
    ) -> int:
        """批量 UPSERT 分块到 pgvector"""
        if not chunks:
            return 0

        from app.database.session import SessionLocal
        if SessionLocal is None:
            logger.warning("Database not initialized, skipping vector store write")
            return 0

        try:
            from sqlalchemy import text
            async with SessionLocal() as session:
                count = 0
                for chunk, emb in zip(chunks, embeddings):
                    await session.execute(text("""
                        INSERT INTO policy_chunks 
                            (chunk_id, policy_id, chunk_index, content, content_hash, 
                             token_count, embedding, metadata)
                        VALUES 
                            (:chunk_id, :policy_id, :chunk_index, :content, :content_hash,
                             :token_count, :embedding, :metadata)
                        ON CONFLICT (chunk_id) DO UPDATE SET
                            content = EXCLUDED.content,
                            embedding = EXCLUDED.embedding,
                            metadata = EXCLUDED.metadata
                    """), {
                        "chunk_id": chunk.chunk_id,
                        "policy_id": chunk.policy_id,
                        "chunk_index": chunk.chunk_index,
                        "content": chunk.content,
                        "content_hash": chunk.content_hash,
                        "token_count": chunk.token_count,
                        "embedding": str(emb),  # pgvector accepts string format
                        "metadata": chunk.metadata,
                    })
                    count += 1
                await session.commit()
                logger.info(f"VectorStore: upserted {count} chunks")
                return count
        except Exception as e:
            logger.error(f"VectorStore upsert failed: {e}")
            return 0

    async def delete_policy_chunks(self, policy_id: str) -> int:
        """删除某政策的所有分块"""
        from app.database.session import SessionLocal
        if SessionLocal is None:
            return 0
        try:
            from sqlalchemy import text
            async with SessionLocal() as session:
                result = await session.execute(
                    text("DELETE FROM policy_chunks WHERE policy_id = :pid"),
                    {"pid": policy_id},
                )
                await session.commit()
                return result.rowcount or 0
        except Exception as e:
            logger.error(f"VectorStore delete failed: {e}")
            return 0

    async def count_chunks(self) -> int:
        """获取总分块数"""
        from app.database.session import SessionLocal
        if SessionLocal is None:
            return 0
        try:
            from sqlalchemy import text
            async with SessionLocal() as session:
                result = await session.execute(text("SELECT COUNT(*) FROM policy_chunks"))
                return result.scalar() or 0
        except Exception:
            return 0

    async def ensure_index(self):
        """确保向量索引存在"""
        from app.database.session import SessionLocal
        if SessionLocal is None:
            return
        try:
            from sqlalchemy import text
            async with SessionLocal() as session:
                await session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_policy_chunks_embedding 
                    ON policy_chunks USING ivfflat (embedding vector_cosine_ops) 
                    WITH (lists = 100)
                """))
                await session.commit()
                logger.info("VectorStore: index ensured")
        except Exception as e:
            logger.warning(f"VectorStore index creation skipped: {e}")
