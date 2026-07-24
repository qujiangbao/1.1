"""KnowledgeTool — 知识库统一访问工具

PolicyAgent 通过 ToolGateway.invoke() → KnowledgeTool → PolicyRetriever → pgvector/Mock
禁止 PolicyAgent 直接访问 pgvector。
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class KnowledgeTool:
    """知识库统一访问工具 — Policy RAG / Industry RAG 的统一入口"""

    def __init__(self):
        self._retriever = None

    @property
    def retriever(self):
        if self._retriever is None:
            from app.services.retriever import PolicyRetriever
            self._retriever = PolicyRetriever()
        return self._retriever

    # ═══ ToolGateway 兼容的同步方法 ═══

    def policy_hybrid_search_sync(self, params: dict) -> dict:
        """混合检索 — ToolGateway 调用入口"""
        import asyncio

        query = str(params.get("query", ""))
        top_k = int(params.get("top_k", 10))
        filters = params.get("filters") if params.get("filters") else None

        try:
            result = asyncio.run(self.retriever.hybrid_search(
                query=query, top_k=top_k, filters=filters,
            ))
        except RuntimeError:
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(
                self.retriever.hybrid_search(query=query, top_k=top_k, filters=filters)
            )
        except Exception as e:
            logger.error(f"KnowledgeTool search failed: {e}")
            return self._error_result("policy_hybrid_search", str(e))

        chunks = result.get("chunks", [])
        return {
            "status": "success",
            "tool": "policy_hybrid_search",
            "params": params,
            "result": {
                "chunks": chunks,
                "total": result.get("total", len(chunks)),
                "mode": result.get("mode", "mock"),
            },
        }

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
