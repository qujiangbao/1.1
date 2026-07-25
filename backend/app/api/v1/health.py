"""Health Check (P8: split liveness/readiness/health)"""
from fastapi import APIRouter
from app.core.llm_warmup import get_warmup_status

router = APIRouter()


@router.get("/health/live")
async def health_live():
    """K8s liveness probe — 进程存活即可返回 200"""
    return {"status": "alive"}


@router.get("/health/ready")
async def health_ready():
    """K8s readiness probe — 核心组件就绪才返回 200"""
    from app.config import get_settings
    s = get_settings()
    components = {}

    # DB check
    if s.database_enabled:
        try:
            from app.tools.database_tool import get_database_tool
            dt = get_database_tool()
            db_ok = await dt.health_check()
            components["database"] = "connected" if db_ok else "disconnected"
        except Exception:
            components["database"] = "error"
    else:
        components["database"] = "disabled"

    # Redis check
    if s.redis_url:
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(s.redis_url)
            await r.ping()
            components["redis"] = "connected"
            await r.close()
        except Exception:
            components["redis"] = "disconnected"
    else:
        components["redis"] = "disabled"

    # LLM check
    ws = get_warmup_status()
    components["llm"] = "ready" if ws.llm_ready else ws.state

    # Determine readiness
    all_ready = all(
        v in ("connected", "disabled", "ready")
        for v in components.values()
    )
    status_code = 200 if all_ready else 503

    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_ready else "not_ready",
            "components": components,
        }
    )


@router.get("/health")
async def health():
    """完整健康信息 — 监控面板用"""
    from app.config import get_settings
    s = get_settings()
    components = {}
    ws = get_warmup_status()

    components["llm"] = {
        "ready": ws.llm_ready,
        "model": ws.model,
        "warmup_ms": ws.warmup_time_ms,
    }

    if s.database_enabled:
        try:
            from app.tools.database_tool import get_database_tool
            dt = get_database_tool()
            components["database"] = "connected" if await dt.health_check() else "disconnected"
        except Exception:
            components["database"] = "error"
    else:
        components["database"] = "disabled"
        components["data_mode"] = "mock"

    return {
        "status": "healthy" if components.get("database", "disabled") != "error" else "degraded",
        "service": "Industrial Park Agent v1.2",
        "components": components,
    }


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
