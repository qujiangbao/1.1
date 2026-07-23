"""Health Check"""
from fastapi import APIRouter

from app.core.llm_warmup import get_warmup_status

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "healthy", "service": "Industrial Park Agent"}


@router.get("/health/warmup")
async def health_warmup():
    """返回 LLM 预热状态。比赛前可调用此端点确认 LLM 已就绪。"""
    ws = get_warmup_status()
    return {
        "status": "ready" if ws.llm_ready else ws.state,
        "llm_ready": ws.llm_ready,
        "warmup_state": ws.state,
        "warmup_time_ms": ws.warmup_time_ms,
        "model": ws.model,
        "error": ws.error,
    }
