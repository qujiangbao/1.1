"""PolicyRetriever — 政策检索引擎

三模式: keyword (tsvector) + vector (cosine) + hybrid (RRF 融合)
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class PolicyRetriever:
    """政策检索引擎 — 唯一直接访问 pgvector 的组件"""

    def __init__(self):
        from app.config import get_settings
        settings = get_settings()
        self.mode = settings.policy_rag_mode  # "mock" | "crawl4ai" | "pgvector"
        self.embedding_provider = settings.policy_embedding_provider
        self.embedding_model = settings.policy_embedding_model
        self.embedding_dimensions = settings.policy_embedding_dimensions
        self.allow_mock_fallback = settings.app_env.lower() != "production"
        self._crawl4ai_data = None

    async def hybrid_search(
        self, query: str, top_k: int = 10, filters: Optional[dict] = None
    ) -> dict:
        """混合检索 — 主入口"""
        # Crawl4AI government policy cache
        if self.mode == "crawl4ai":
            try:
                from app.tools.adapters.policy_crawl4ai import PolicyCrawl4AIData
                if self._crawl4ai_data is None:
                    self._crawl4ai_data = PolicyCrawl4AIData()
                chunks = self._crawl4ai_data.search(query=query, filters=filters, top_k=top_k)
                return {"chunks": chunks, "total": len(chunks), "mode": "crawl4ai"}
            except Exception:
                logger.exception("Crawl4AI policy search failed")
                if not self.allow_mock_fallback:
                    raise
                fallback = self._mock_search(query, filters, top_k)
                fallback["mode"] = "mock_fallback"
                return fallback

        # Mock mode
        if self.mode == "mock":
            return self._mock_search(query, filters, top_k)

        # pgvector 模式
        try:
            return await self._pgvector_hybrid_search(query, top_k, filters)
        except Exception:
            logger.exception("pgvector search failed")
            if not self.allow_mock_fallback:
                raise
            fallback = self._mock_search(query, filters, top_k)
            fallback["mode"] = "mock_fallback"
            return fallback

    # ── pgvector 实现 ──────────────────────

    async def _pgvector_hybrid_search(
        self, query: str, top_k: int, filters: Optional[dict]
    ) -> dict:
        from app.services.embedding import EmbeddingService

        # 1. 查询向量化
        emb_svc = EmbeddingService(
            provider=self.embedding_provider,
            model=self.embedding_model,
            dimensions=self.embedding_dimensions,
        )
        query_vec = await emb_svc.embed_batch([query])
        query_embedding = query_vec[0]

        # 2. pgvector cosine similarity
        from app.database.session import SessionLocal
        if SessionLocal is None:
            raise RuntimeError("Database is not initialized for pgvector retrieval")

        from sqlalchemy import text
        async with SessionLocal() as session:
            # 构建 WHERE 条件
            conditions = []
            params = {
                "query_vec": "[" + ",".join(str(value) for value in query_embedding) + "]",
                "top_k": top_k * 2,  # 多取一些供 RRF
            }

            if filters:
                if filters.get("level"):
                    conditions.append("p.level = :level")
                    params["level"] = filters["level"]
                if filters.get("active_only") is not False:
                    conditions.append("(p.status = 'active')")
                if filters.get("department"):
                    conditions.append("p.department = :dept")
                    params["dept"] = filters["department"]

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            sql = f"""
                SELECT 
                    pc.chunk_id, pc.policy_id, pc.chunk_index, pc.content,
                    1 - (pc.embedding <=> CAST(:query_vec AS vector)) AS score,
                    pc.metadata,
                    'vector' AS search_method
                FROM policy_chunks pc
                JOIN policy p ON pc.policy_id = p.policy_id
                WHERE pc.embedding IS NOT NULL AND {where_clause}
                ORDER BY pc.embedding <=> CAST(:query_vec AS vector)
                LIMIT :top_k
            """

            result = await session.execute(text(sql), params)
            rows = result.fetchall()

        # 3. 地区/行业内存过滤 + 重排
        chunks = []
        for row in rows:
            chunk_meta = row.metadata or {}
            # 地区过滤
            if filters and filters.get("region"):
                region = str(filters["region"]).lower()
                meta_region = str(chunk_meta.get("region_scope", "")).lower()
                if region not in meta_region:
                    continue
            # 行业过滤
            if filters and filters.get("industry"):
                ind = str(filters["industry"]).lower()
                meta_ind = str(chunk_meta.get("industry_scope", "")).lower()
                if ind not in meta_ind:
                    continue

            chunks.append({
                "chunk_id": row.chunk_id,
                "policy_id": row.policy_id,
                "chunk_index": row.chunk_index,
                "content": row.content,
                "score": round(float(row.score), 4),
                "search_method": "vector",
                "metadata": dict(chunk_meta),
                "evidence": [{
                    "type": "pgvector",
                    "value": f"cosine_similarity={row.score:.4f}",
                    "url": chunk_meta.get("source_url", ""),
                }],
            })

        # 去重 (每个 policy 取最高分 chunk)
        seen = {}
        for c in sorted(chunks, key=lambda x: -x["score"]):
            pid = c["policy_id"]
            if pid not in seen:
                seen[pid] = c

        result_chunks = list(seen.values())[:top_k]
        return {"chunks": result_chunks, "total": len(result_chunks), "mode": "pgvector"}

    # ── Mock 实现 ──────────────────────────

    def _mock_search(self, query: str, filters: Optional[dict], top_k: int) -> dict:
        from app.tools.adapters.policy_mock import PolicyMockData
        chunks = PolicyMockData.search(query=query, filters=filters, top_k=top_k)
        return {"chunks": chunks, "total": len(chunks), "mode": "mock"}
