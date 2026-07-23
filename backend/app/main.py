from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.config import get_settings
from app.core.logger import setup_logger

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logger(settings.log_level)
    logger.info("Industrial Park Agent starting...")
    from app.agents.registry import init_agent_registry
    await init_agent_registry()

    if settings.database_enabled:
        from app.database.session import init_db
        await init_db(settings.database_url)

    # LLM Warmup — 后台预热，不阻塞启动
    if settings.llm_warmup_enabled and (settings.openai_api_key or settings.deepseek_api_key):
        from app.core.llm_warmup import start_warmup
        start_warmup()
    yield
    if settings.database_enabled:
        from app.database.session import close_db
        await close_db()
    logger.info("Industrial Park Agent shutting down...")


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="广州产业AI运营官 — Multi-Agent Backend",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.v1 import router as v1_router
app.include_router(v1_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"service": "Industrial Park Agent", "status": "running"}
