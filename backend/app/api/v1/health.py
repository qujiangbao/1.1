"""Health Check (P6: enhanced with DB status)"""
from fastapi import APIRouter
from app.core.llm_warmup import get_warmup_status

router = APIRouter()


@router.get("/health")
async def health():
    """System health — includes DB connectivity check"""
    status = {"status": "healthy", "service": "Industrial Park Agent v1.2"}
    # P6: DB health check
    from app.config import get_settings
    s = get_settings()
    if s.database_enabled:
        try:
            from app.tools.database_tool import get_database_tool
            dt = get_database_tool()
            db_ok = await dt.health_check()
            status["database"] = "connected" if db_ok else "disconnected"
        except Exception:
            status["database"] = "error"
    return status


@router.get("/health/warmup")
async def health_warmup():
    """LLM warmup status"""
    ws = get_warmup_status()
    return {
        "status": "ready" if ws.llm_ready else ws.state,
        "llm_ready": ws.llm_ready,
        "warmup_state": ws.state,
        "warmup_time_ms": ws.warmup_time_ms,
        "model": ws.model,
        "error": ws.error,
    }
