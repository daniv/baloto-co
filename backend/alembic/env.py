"""Alembic migration environment, wired to the application's async engine and settings."""

import asyncio
from logging.config import fileConfig
from typing import TYPE_CHECKING

from alembic import context
from app.core.config import settings
from app.core.database import Base
from app.games import models  # noqa: F401 # pyright: ignore[reportUnusedImport]  # registers ORM tables
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The DB URL always comes from app.core.config.settings, not alembic.ini,
# so there is exactly one place that assembles the connection string.
config.set_main_option("sqlalchemy.url", str(settings.pg_dsn))

# app.games.models is imported above purely for its side effect of
# registering every table on Base.metadata before autogenerate compares
# it against the live database. Any future model module needs the same.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit migration SQL against a URL only, without an active DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations synchronously against an already-open sync connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Open an async engine and delegate migration execution to a sync connection."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
