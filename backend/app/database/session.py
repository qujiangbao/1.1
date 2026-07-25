from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

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

    # P5: Run Alembic migrations instead of create_all
    _run_migrations()

    # P4: Seed RBAC data
    async with SessionLocal() as session:
        from app.database.models.rbac import seed_rbac_data
        await seed_rbac_data(session)


def _run_migrations():
    """Execute Alembic migrations programmatically"""
    import os
    from alembic.config import Config
    from alembic import command

    migrations_path = os.path.join(os.path.dirname(__file__), "..", "..", "migrations")
    alembic_ini = os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini")

    if not os.path.exists(alembic_ini):
        return  # Migration not configured

    alembic_cfg = Config(alembic_ini)
    alembic_cfg.set_main_option("script_location", migrations_path)

    try:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(command.upgrade, alembic_cfg, "head")
            future.result(timeout=60)
    except Exception:
        pass  # Allow startup without DB (demo mode)


async def close_db():
    if engine:
        await engine.dispose()


async def get_db() -> AsyncSession:
    if SessionLocal is None:
        raise RuntimeError("Database is disabled or has not been initialized")
    async with SessionLocal() as session:
        yield session
