"""Alembic env.py — P5 Async PostgreSQL Migration

Replaces Base.metadata.create_all() with proper Alembic migrations.
Supports: upgrade, downgrade, auto-generate from models."""

import asyncio
from logging.config import fileConfig
from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

# Alembic Config
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models to register metadata
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.database.session import Base
import app.database.models  # noqa: F401 — registers all tables

target_metadata = Base.metadata


def get_url() -> str:
    """Get database URL from config or environment"""
    from app.config import get_settings
    settings = get_settings()
    return settings.database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generate SQL without DB connection)"""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """Execute migrations within a transaction"""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode (with async DB connection)"""
    url = get_url()
    connectable = create_async_engine(url, poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Online migration entry point"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
