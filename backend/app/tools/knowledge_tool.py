"""KnowledgeTool — 知识库统一访问工具

PolicyAgent 通过 ToolGateway.invoke() → KnowledgeTool → PolicyRetriever → pgvector/Mock
禁止 PolicyAgent 直接访问 pgvector。
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging

logger = logging.getLogger(__name__)


class KnowledgeTool:
    """知识库统一访问工具 — Policy RAG / Industry RAG 的统一入口"""

    def __init__(self):
        self._retriever = None
        self._event_loop: asyncio.AbstractEventLoop | None = None

    def bind_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind sync ToolGateway calls to the application's async I/O loop."""
        self._event_loop = loop

    def unbind_event_loop(self) -> None:
        self._event_loop = None

    @property
    def retriever(self):
        if self._retriever is None:
            from app.services.retriever import PolicyRetriever
            self._retriever = PolicyRetriever()
        return self._retriever

    # ═══ ToolGateway 兼容的同步方法 ═══

    async def policy_hybrid_search(self, params: dict) -> dict:
        """异步混合检索 — FastAPI 与异步调用方的主入口"""
        query = str(params.get("query", ""))
        top_k = int(params.get("top_k", 10))
        filters = params.get("filters") if params.get("filters") else None

        try:
            result = await self.retriever.hybrid_search(
                query=query, top_k=top_k, filters=filters,
            )
        except Exception as e:
            logger.error(f"KnowledgeTool search failed: {e}")
            return self._error_result("policy_hybrid_search", str(e))

        chunks = result.get("chunks", [])
        # Park-owned material is searched locally and merged with the public
        # policy source. This keeps private documents usable even when the
        # deployment cannot afford a second vector service.
        try:
            from app.services.park_document_service import search_park_documents
            # PolicyAgent must not treat an enterprise due-diligence report as
            # a policy merely because both texts contain generic terms such as
            # "广州" or "企业".
            private_chunks = search_park_documents(
                query,
                max(3, top_k // 2),
                purpose="policy",
            )
        except Exception:
            logger.exception("Park document search failed")
            private_chunks = []
        chunks = sorted(
            [*chunks, *private_chunks],
            key=lambda item: float(item.get("score") or item.get("match_score", 0) / 100),
            reverse=True,
        )[:top_k]
        return {
            "status": "success",
            "tool": "policy_hybrid_search",
            "params": params,
            "result": {
                "chunks": chunks,
                "total": result.get("total", len(chunks)),
                "mode": (
                    f"{result.get('mode', 'mock')}+park_documents"
                    if private_chunks else result.get("mode", "mock")
                ),
            },
        }

    def policy_hybrid_search_sync(self, params: dict) -> dict:
        """同步兼容入口，供 ToolGateway 的同步节点调用。"""
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        # LangGraph executes synchronous nodes in worker threads. Schedule
        # database I/O back onto the FastAPI loop that owns the asyncpg pool.
        bound_loop = self._event_loop
        if bound_loop is not None and bound_loop.is_running():
            if current_loop is bound_loop:
                raise RuntimeError(
                    "Use policy_hybrid_search() from the application event loop"
                )
            future = asyncio.run_coroutine_threadsafe(
                self.policy_hybrid_search(params),
                bound_loop,
            )
            return future.result()

        if current_loop is None:
            return asyncio.run(self.policy_hybrid_search(params))

        # A synchronous graph node may be called from an active event loop.
        # Execute the coroutine in an isolated thread instead of nesting loops.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(
                asyncio.run,
                self.policy_hybrid_search(params),
            ).result()

    def policy_keyword_search_sync(self, params: dict) -> dict:
        """关键词检索 — 委托给 hybrid_search"""
        return self.policy_hybrid_search_sync(params)

    def policy_vector_search_sync(self, params: dict) -> dict:
        """向量检索 — 委托给 hybrid_search（兼容旧名称）"""
        return self.policy_hybrid_search_sync(params)

    def policy_metadata_search_sync(self, params: dict) -> dict:
        """元数据检索 — 委托给 hybrid_search（兼容旧名称）"""
        return self.policy_hybrid_search_sync(params)

    def policy_query_sync(self, params: dict) -> dict:
        """政策查询 — 委托给 hybrid_search（兼容旧名称）"""
        return self.policy_hybrid_search_sync(params)

    # ═══ 辅助 ═══

    def _error_result(self, tool_name: str, error_msg: str) -> dict:
        return {
            "status": "error",
            "tool": tool_name,
            "error": error_msg,
            "result": {"chunks": [], "total": 0, "mode": "error"},
        }


# 全局单例
_kt: KnowledgeTool | None = None


def get_knowledge_tool() -> KnowledgeTool:
    global _kt
    if _kt is None:
        _kt = KnowledgeTool()
    return _kt
