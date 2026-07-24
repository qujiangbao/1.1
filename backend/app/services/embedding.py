"""EmbeddingService — 文本向量化

支持: OpenAI text-embedding-3-small, DeepSeek, 本地 fallback
"""
from __future__ import annotations

import logging
from typing import List

logger = logging.getLogger(__name__)


class EmbeddingService:
    """文本向量化服务"""

    def __init__(self, provider: str = "deepseek", model: str = "", dimensions: int = 1536):
        self.provider = provider
        self.model = model or "text-embedding-3-small"
        self.dimensions = dimensions

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量向量化"""
        if not texts:
            return []

        if self.provider == "mock":
            return self._mock_embed(texts)

        try:
            if self.provider == "deepseek":
                return await self._deepseek_embed(texts)
            elif self.provider == "openai":
                return await self._openai_embed(texts)
            else:
                logger.warning(f"Unknown provider {self.provider}, using mock")
                return self._mock_embed(texts)
        except Exception as e:
            logger.error(f"Embedding failed: {e}, falling back to mock")
            return self._mock_embed(texts)

    def embed_sync(self, texts: List[str]) -> List[List[float]]:
        """同步向量化 (ToolGateway 兼容)"""
        import asyncio
        try:
            return asyncio.run(self.embed_batch(texts))
        except RuntimeError:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.embed_batch(texts))

    async def _openai_embed(self, texts: List[str]) -> List[List[float]]:
        from app.config import get_settings
        settings = get_settings()
        if not settings.openai_api_key:
            raise ValueError("OpenAI API Key not configured")

        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={"input": texts, "model": self.model},
                timeout=30,
            )
            data = resp.json()
            return [d["embedding"] for d in data["data"]]

    async def _deepseek_embed(self, texts: List[str]) -> List[List[float]]:
        """DeepSeek 兼容 OpenAI Embedding API"""
        from app.config import get_settings
        settings = get_settings()
        if not settings.deepseek_api_key:
            raise ValueError("DeepSeek API Key not configured")

        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.deepseek_base_url}/embeddings",
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
                json={"input": texts, "model": self.model},
                timeout=30,
            )
            data = resp.json()
            return [d["embedding"] for d in data["data"]]

    def _mock_embed(self, texts: List[str]) -> List[List[float]]:
        """Mock: 基于文本 hash 的确定性假向量 (测试用)"""
        import hashlib
        results = []
        for text in texts:
            h = hashlib.sha256(text.encode()).digest()
            vec = [(b / 255.0) * 2 - 1 for b in h[:self.dimensions]]
            # 补零到目标维度
            if len(vec) < self.dimensions:
                vec.extend([0.0] * (self.dimensions - len(vec)))
            results.append(vec[:self.dimensions])
        return results
