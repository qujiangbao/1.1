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
        self.model_validation: Dict[str, dict] = {}
        self._available_models = self._detect_available()

    def _detect_available(self) -> list:
        available = []
        if self.settings.deepseek_api_key and self.settings.deepseek_api_key != "***":
            available.append(self.deepseek_model)
            self._key_cache["deepseek"] = self.settings.deepseek_api_key
        if self.settings.openai_api_key and self.settings.openai_api_key != "***" and len(self.settings.openai_api_key) > 20:
            available.append(self.settings.openai_model)
            self._key_cache["openai"] = self.settings.openai_api_key
        logger.info("[LLM] Available models: %s", available or ["keyword fallback only"])
        return available

    def _models_for_task(self, task_type: str) -> list[str]:
        """P8: 动态模型优先级，不硬编码模型名"""
        candidates = [self.deepseek_model, self.settings.openai_model]
        return list(dict.fromkeys(candidates))

    def _get_key_for(self, model: str) -> str:
        if model == self.deepseek_model:
            return self.settings.deepseek_api_key
        return self.settings.openai_api_key

    def _get_base_url(self, model: str) -> Optional[str]:
        if model == self.deepseek_model:
            return self.settings.deepseek_base_url
        return None

    async def validate_configured_models(self) -> dict:
        """Validate configured model IDs through provider model-list APIs."""
        import httpx

        providers = []
        if "deepseek" in self._key_cache:
            providers.append(
                (
                    "deepseek",
                    self.settings.deepseek_base_url.rstrip("/"),
                    self.settings.deepseek_api_key,
                    self.deepseek_model,
                )
            )
        if "openai" in self._key_cache:
            providers.append(
                (
                    "openai",
                    "https://api.openai.com/v1",
                    self.settings.openai_api_key,
                    self.settings.openai_model,
                )
            )

        async with httpx.AsyncClient(timeout=10) as client:
            for provider, base_url, api_key, model in providers:
                try:
                    response = await client.get(
                        f"{base_url}/models",
                        headers={"Authorization": f"Bearer {api_key}"},
                    )
                    response.raise_for_status()
                    payload = response.json()
                    available = {
                        item.get("id")
                        for item in payload.get("data", [])
                        if isinstance(item, dict)
                    }
                    if model not in available:
                        raise ValueError(
                            f"{provider} model is unavailable: {model}"
                        )
                    self.model_validation[provider] = {
                        "status": "ready",
                        "model": model,
                    }
                except Exception as exc:
                    self.model_validation[provider] = {
                        "status": "failed",
                        "model": model,
                        "error": str(exc),
                    }
                    raise
        return self.get_model_validation_report()

    def get_model_validation_report(self) -> dict:
        return {
            "configured": list(self._key_cache),
            "providers": dict(self.model_validation),
        }

    def invoke_sync(self, agent_name: str, task_type: str, prompt: str,
                    max_tokens: int = 2000, temperature: float = 0.2) -> LLMResult:
        import asyncio
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.invoke(agent_name, task_type, prompt, max_tokens, temperature))
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(
                lambda: asyncio.run(self.invoke(agent_name, task_type, prompt, max_tokens, temperature))
            ).result(timeout=70)

    async def invoke(self, agent_name: str, task_type: str, prompt: str,
                     max_tokens: int = 2000, temperature: float = 0.2) -> LLMResult:
        models = self._models_for_task(task_type)
        eligible_models = [model for model in models if model in self._available_models]
        if not eligible_models:
            raise RuntimeError("LLM Gateway: no model is configured")

        # Avoid importing the relatively heavy client when deterministic
        # fallback is the only available mode.
        from langchain_openai import ChatOpenAI

        for model_name in eligible_models:
            base_url = self._get_base_url(model_name)
            api_key = self._get_key_for(model_name)

            try:
                t0 = time.time()
                kwargs = dict(
                    model=model_name,
                    api_key=api_key,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=60,
                    max_retries=2,
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
