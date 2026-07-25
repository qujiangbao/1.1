"""LLM Gateway — 统一 LLM 调用入口，支持 OpenAI + DeepSeek (P8: 动态模型配置)"""
import time
import logging
from typing import Optional, Dict
from dataclasses import dataclass
from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResult:
    model: str
    content: str
    token_count: int
    cost: float
    latency_ms: int


class LLMGateway:
    """P8: 模型配置完全来自 Settings，不再硬编码模型名"""

    def __init__(self):
        self.settings = get_settings()
        self.deepseek_model = self.settings.deepseek_model
        self.usage_stats: Dict[str, dict] = {}
        self._key_cache: Dict[str, str] = {}
        self._available_models = self._detect_available()

    def _detect_available(self) -> list:
        available = []
        if self.settings.deepseek_api_key and self.settings.deepseek_api_key != "***":
            available.append(self.deepseek_model)
            self._key_cache["deepseek"] = self.settings.deepseek_api_key
        if self.settings.openai_api_key and self.settings.openai_api_key != "***" and len(self.settings.openai_api_key) > 20:
            available.append("gpt-4o-mini")
            self._key_cache["openai"] = self.settings.openai_api_key
        logger.info("[LLM] Available models: %s", available or ["keyword fallback only"])
        return available

    def _models_for_task(self, task_type: str) -> list[str]:
        """P8: 动态模型优先级，不硬编码模型名"""
        if task_type == "reasoning":
            return [self.deepseek_model, self.settings.openai_model, "gpt-4o-mini"]
        if task_type == "simple":
            return [self.deepseek_model, "gpt-4o-mini"]
        return [self.deepseek_model]

    def _get_key_for(self, model: str) -> str:
        if model == self.deepseek_model:
            return self.settings.deepseek_api_key
        return self.settings.openai_api_key

    def _get_base_url(self, model: str) -> Optional[str]:
        if model == self.deepseek_model:
            return self.settings.deepseek_base_url
        return None

    def invoke_sync(self, agent_name: str, task_type: str, prompt: str,
                    max_tokens: int = 2000, temperature: float = 0.2) -> LLMResult:
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

        models = self._models_for_task(task_type)

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
                logger.info("[LLM] %s → %s (%sms, %s chars)", agent_name, model_name, latency, len(content))
                stats = self.usage_stats.setdefault(agent_name, {"calls": 0, "tokens": 0})
                stats["calls"] += 1
                stats["tokens"] += len(content) // 2
                return LLMResult(model=model_name, content=content, token_count=len(content)//2, cost=0, latency_ms=latency)

            except Exception as e:
                logger.warning("[LLM] %s failed: %s", model_name, e)
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
