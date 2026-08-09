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

    # DB is optional in the documented local/crawl4ai mode, but mandatory
    # when pgvector retrieval is selected.
    database_required = s.database_enabled or s.policy_rag_mode == "pgvector"
    if s.database_enabled:
        try:
            from app.tools.database_tool import get_database_tool
            dt = get_database_tool()
            db_ok = await dt.health_check()
            components["database"] = "connected" if db_ok else "disconnected"
        except Exception:
            components["database"] = "error"
    elif database_required:
        components["database"] = "required_but_disabled"
    else:
        components["database"] = "disabled"

    # Redis is only a readiness dependency when streaming is enabled.
    if s.streaming_enabled and s.redis_url:
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(s.redis_url)
            await r.ping()
            components["redis"] = "connected"
            await r.close()
        except Exception:
            components["redis"] = "disconnected"
    elif s.streaming_enabled:
        components["redis"] = "required_but_disabled"
    else:
        components["redis"] = "disabled"

    # LLM check. The documented deterministic fallback is a valid runtime
    # mode when no provider key is configured.
    ws = get_warmup_status()
    if not s.openai_api_key and not s.deepseek_api_key:
        components["llm"] = "fallback"
    elif not s.llm_warmup_enabled:
        components["llm"] = "disabled"
    else:
        components["llm"] = "ready" if ws.llm_ready else ws.state

    # Determine readiness
    all_ready = all(
        v in ("connected", "disabled", "ready", "fallback")
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
    if s.openai_api_key or s.deepseek_api_key:
        from app.core.llm_gateway import get_llm_gateway
        components["llm"]["validation"] = (
            get_llm_gateway().get_model_validation_report()
        )

    if s.database_enabled:
        try:
            from app.tools.database_tool import get_database_tool
            dt = get_database_tool()
            components["database"] = "connected" if await dt.health_check() else "disconnected"
        except Exception:
            components["database"] = "error"
    else:
        components["database"] = "disabled"
        components["data_mode"] = "runtime"

    return {
        "status": "healthy" if components.get("database", "disabled") != "error" else "degraded",
        "service": "Industrial Park Agent v1.3",
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
