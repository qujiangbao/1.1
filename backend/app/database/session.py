from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
import asyncio
import logging

logger = logging.getLogger(__name__)

engine = None
SessionLocal = None


class Base(DeclarativeBase):
    pass


async def init_db(database_url: str):
    """P5: 使用 Alembic migrations 替代 create_all"""
    global engine, SessionLocal
    import app.database.models  # noqa: F401 — register all tables
    engine = create_async_engine(database_url, echo=False, pool_size=10)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    try:
        # Alembic's async environment owns its event loop, so run it outside
        # FastAPI's active loop. Any failure must abort database-enabled startup.
        await asyncio.to_thread(_run_migrations)

        # P4: Seed RBAC data
        async with SessionLocal() as session:
            from app.database.models.rbac import seed_rbac_data
            await seed_rbac_data(session)
    except Exception:
        logger.exception("Database initialization failed")
        await engine.dispose()
        engine = None
        SessionLocal = None
        raise


def _run_migrations():
    """Execute Alembic migrations programmatically"""
    import os
    from alembic.config import Config
    from alembic import command

    migrations_path = os.path.join(os.path.dirname(__file__), "..", "..", "migrations")
    alembic_ini = os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini")

    if not os.path.exists(alembic_ini):
        raise FileNotFoundError(f"Alembic configuration not found: {alembic_ini}")

    alembic_cfg = Config(alembic_ini)
    alembic_cfg.set_main_option("script_location", migrations_path)

    command.upgrade(alembic_cfg, "head")


async def close_db():
    if engine:
        await engine.dispose()


async def get_db() -> AsyncSession:
    if SessionLocal is None:
        raise RuntimeError("Database is disabled or has not been initialized")
    async with SessionLocal() as session:
        yield session
