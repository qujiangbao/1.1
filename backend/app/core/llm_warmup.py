"""LLM Warmup Service — 启动时自动预热 LLM 连接池和 Model Session"""
import time
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class WarmupStatus:
    state: str = "pending"          # pending | warming_up | ready | failed
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    warmup_time_ms: Optional[int] = None
    model: Optional[str] = None
    error: Optional[str] = None
    llm_ready: bool = False


_warmup: WarmupStatus = WarmupStatus()


def get_warmup_status() -> WarmupStatus:
    return _warmup


async def _do_warmup():
    """发送轻量测试请求，预热 LLM 连接池"""
    global _warmup
    _warmup.state = "warming_up"
    _warmup.started_at = time.time()
    t0 = time.time()

    try:
        from app.core.llm_gateway import get_llm_gateway
        gateway = get_llm_gateway()

        logger.info("[Warmup] Starting LLM warmup...")

        # 轻量测试 prompt — 极短，只为了建立连接和 Session
        result = await gateway.invoke(
            agent_name="WarmupService",
            task_type="simple",
            prompt="OK",
            max_tokens=10,
            temperature=0.0,
        )

        elapsed = int((time.time() - t0) * 1000)
        _warmup.state = "ready"
        _warmup.llm_ready = True
        _warmup.model = result.model
        _warmup.warmup_time_ms = elapsed
        _warmup.finished_at = time.time()

        logger.info(f"[Warmup] ✅ LLM ready — {result.model} in {elapsed}ms")

    except Exception as e:
        elapsed = int((time.time() - t0) * 1000)
        _warmup.state = "failed"
        _warmup.error = str(e)
        _warmup.finished_at = time.time()
        _warmup.warmup_time_ms = elapsed

        logger.warning(f"[Warmup] ⚠️ LLM warmup failed ({elapsed}ms): {e}")
        logger.warning("[Warmup] System will use fallback mode — first real request may be slow")


def start_warmup():
    """在 FastAPI lifespan 中调用，启动后台预热任务"""
    global _warmup
    if _warmup.state == "pending":
        asyncio.create_task(_do_warmup())
        logger.info("[Warmup] Background warmup task scheduled")
