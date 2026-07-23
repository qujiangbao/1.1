"""LLM Gateway — 统一 LLM 调用入口，支持 OpenAI + DeepSeek"""
import time
import logging
from typing import Optional, Dict
from dataclasses import dataclass
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class LLMResult:
    model: str
    content: str
    token_count: int
    cost: float
    latency_ms: int


class LLMGateway:
    """
    模型优先级：
    1. DeepSeek (国内可用，便宜) — 如果配置了 deepseek_api_key
    2. OpenAI gpt-4o-mini — 如果配置了 openai_api_key
    3. 关键词兜底 — 无需 API Key
    """

    MODEL_PRIORITY = {
        "reasoning": ["deepseek-chat", "gpt-4o", "gpt-4o-mini"],
        "simple":    ["deepseek-chat", "gpt-4o-mini"],
        "embedding": ["text-embedding-3-small"],
    }

    MODEL_CONFIG = {
        "deepseek-chat":   {"base_url": "https://api.deepseek.com/v1", "key_attr": "deepseek_api_key"},
        "gpt-4o":          {"base_url": None, "key_attr": "openai_api_key"},
        "gpt-4o-mini":     {"base_url": None, "key_attr": "openai_api_key"},
        "text-embedding-3-small": {"base_url": None, "key_attr": "openai_api_key"},
    }

    def __init__(self):
        self.usage_stats: Dict[str, dict] = {}
        self._key_cache: Dict[str, str] = {}
        self._available_models = self._detect_available()

    def _detect_available(self) -> list:
        """检测哪些模型的 API Key 已配置"""
        available = []
        if settings.deepseek_api_key and settings.deepseek_api_key != "***":
            available.append("deepseek-chat")
            self._key_cache["deepseek"] = settings.deepseek_api_key
        if settings.openai_api_key and settings.openai_api_key != "***" and len(settings.openai_api_key) > 20:
            available.append("gpt-4o")
            available.append("gpt-4o-mini")
            self._key_cache["openai"] = settings.openai_api_key
        logger.info(f"[LLM] Available models: {available or ['keyword fallback only']}")
        return available

    def _get_key_for(self, model: str) -> str:
        cfg = self.MODEL_CONFIG.get(model, {})
        attr = cfg.get("key_attr", "openai_api_key")
        if attr == "deepseek_api_key":
            return settings.deepseek_api_key
        return settings.openai_api_key

    def _get_base_url(self, model: str) -> Optional[str]:
        if model == "deepseek-chat":
            return settings.deepseek_base_url
        return self.MODEL_CONFIG.get(model, {}).get("base_url")

    def invoke_sync(self, agent_name: str, task_type: str, prompt: str,
                    max_tokens: int = 2000, temperature: float = 0.2) -> LLMResult:
        """同步调用 LLM"""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.invoke(agent_name, task_type, prompt, max_tokens, temperature))
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(
                lambda: asyncio.run(self.invoke(agent_name, task_type, prompt, max_tokens, temperature))
            ).result(timeout=35)

    async def invoke(self, agent_name: str, task_type: str, prompt: str,
                     max_tokens: int = 2000, temperature: float = 0.2) -> LLMResult:
        from langchain_openai import ChatOpenAI

        models = self.MODEL_PRIORITY.get(task_type, ["deepseek-chat"])

        for model_name in models:
            if model_name not in self._available_models:
                continue

            base_url = self._get_base_url(model_name)
            api_key = self._get_key_for(model_name)

            try:
                t0 = time.time()
                kwargs = dict(
                    model=model_name,
                    api_key=api_key,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=30,
                    max_retries=1,
                )
                if base_url:
                    kwargs["base_url"] = base_url

                llm = ChatOpenAI(**kwargs)
                resp = await llm.ainvoke([("user", prompt)])
                content = resp.content

                latency = int((time.time() - t0) * 1000)
                logger.info(f"[LLM] {agent_name} → {model_name} ({latency}ms, {len(content)} chars)")
                stats = self.usage_stats.setdefault(agent_name, {"calls": 0, "tokens": 0})
                stats["calls"] += 1
                stats["tokens"] += len(content) // 2
                return LLMResult(model=model_name, content=content, token_count=len(content)//2, cost=0, latency_ms=latency)

            except Exception as e:
                logger.warning(f"[LLM] {model_name} failed: {e}")
                continue

        raise RuntimeError("LLM Gateway: no available model succeeded")

    def get_usage_report(self) -> dict:
        return {"by_agent": self.usage_stats, "total_cost": 0}


_llm_gateway: Optional[LLMGateway] = None


def get_llm_gateway() -> LLMGateway:
    global _llm_gateway
    if _llm_gateway is None:
        _llm_gateway = LLMGateway()
    return _llm_gateway
