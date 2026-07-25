from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

engine = None
SessionLocal = None


class Base(DeclarativeBase):
    pass


async def init_db(database_url: str):
    global engine, SessionLocal
    # Ensure all table metadata is registered before create_all.
    import app.database.models  # noqa: F401
    engine = create_async_engine(database_url, echo=False, pool_size=10)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # P4: Seed RBAC data
    async with SessionLocal() as session:
        from app.database.models.rbac import seed_rbac_data
        await seed_rbac_data(session)


async def close_db():
    if engine:
        await engine.dispose()


async def get_db() -> AsyncSession:
    if SessionLocal is None:
        raise RuntimeError("Database is disabled or has not been initialized")
    async with SessionLocal() as session:
        yield session
