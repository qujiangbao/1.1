"""EmbeddingService — 文本向量化

支持: 阿里云百炼 text-embedding-v4、OpenAI text-embedding-3-small；
mock 仅用于显式测试
"""
from __future__ import annotations

import logging
from typing import List

logger = logging.getLogger(__name__)


class EmbeddingService:
    """文本向量化服务"""

    def __init__(
        self,
        provider: str = "dashscope",
        model: str = "",
        dimensions: int = 1536,
    ):
        self.provider = provider.strip().lower()
        self.model = model or (
            "text-embedding-v4"
            if self.provider == "dashscope"
            else "text-embedding-3-small"
        )
        self.dimensions = dimensions

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量向量化"""
        if not texts:
            return []

        if self.provider == "mock":
            return self._mock_embed(texts)

        try:
            if self.provider == "openai":
                embeddings = await self._openai_embed(texts)
            elif self.provider == "dashscope":
                embeddings = await self._dashscope_embed(texts)
            else:
                raise ValueError(f"Unknown embedding provider: {self.provider}")
        except Exception:
            logger.exception("Policy embedding request failed")
            raise

        if len(embeddings) != len(texts):
            raise ValueError("Embedding provider returned an unexpected item count")
        if any(len(vector) != self.dimensions for vector in embeddings):
            raise ValueError(
                f"Embedding provider must return {self.dimensions}-dimension vectors"
            )
        return embeddings

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
            resp.raise_for_status()
            data = resp.json()
            return [d["embedding"] for d in data["data"]]

    async def _dashscope_embed(self, texts: List[str]) -> List[List[float]]:
        from app.config import get_settings

        settings = get_settings()
        if not settings.dashscope_api_key:
            raise ValueError("DashScope API Key not configured")
        base_url = settings.dashscope_base_url.strip().rstrip("/")
        if not base_url:
            raise ValueError("DashScope base URL not configured")

        import httpx

        embeddings: List[List[float]] = []
        async with httpx.AsyncClient() as client:
            for start in range(0, len(texts), 10):
                batch = texts[start:start + 10]
                resp = await client.post(
                    f"{base_url}/embeddings",
                    headers={
                        "Authorization": (
                            f"Bearer {settings.dashscope_api_key}"
                        )
                    },
                    json={
                        "input": batch,
                        "model": self.model,
                        "dimensions": self.dimensions,
                        "encoding_format": "float",
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
                items = data.get("data")
                if not isinstance(items, list):
                    raise ValueError(
                        "DashScope returned an invalid embedding response"
                    )
                ordered = sorted(
                    items,
                    key=lambda item: int(item.get("index", 0)),
                )
                embeddings.extend(item["embedding"] for item in ordered)
        return embeddings

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
