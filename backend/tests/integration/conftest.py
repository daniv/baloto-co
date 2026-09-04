"""
Shared fixtures for HTTP-level integration tests against the real FastAPI app.

Tests here hit the app over ASGI (via ``httpx.AsyncClient``) and a real,
disposable Postgres database (``settings.db_name_test``), rather than
mocking the DB or the router layer, so they exercise the actual dependency
wiring (auth, session, error mapping) end to end.
"""

from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.core.config import settings
from app.core.database import Base, get_session
from app.main import app

_MAINTENANCE_DB = "postgres"


def _dsn(db_name: str) -> str:
    """Build an asyncpg DSN for ``db_name`` using the configured DB credentials."""
    password = settings.db_password.get_secret_value()
    return f"postgresql+asyncpg://{settings.db_user}:{password}@{settings.db_host}:{settings.db_port}/{db_name}"


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine]:
    """
    Create the disposable test database and its schema once per test session.

    Connects to the ``postgres`` maintenance database to create
    ``settings.db_name_test`` if it doesn't already exist (``CREATE
    DATABASE`` can't run inside a transaction, hence the ``AUTOCOMMIT``
    isolation level), then creates every table from :attr:`Base.metadata`
    against it. The schema is dropped and the engine disposed at the end
    of the session.

    :return: Async generator yielding the engine bound to the test database.
    """
    maintenance_engine = create_async_engine(_dsn(_MAINTENANCE_DB), isolation_level="AUTOCOMMIT")
    async with maintenance_engine.connect() as connection:
        exists = await connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": settings.db_name_test}
        )
        if exists.first() is None:
            await connection.exec_driver_sql(f'CREATE DATABASE "{settings.db_name_test}"')
    await maintenance_engine.dispose()

    engine = create_async_engine(_dsn(settings.db_name_test))
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    """
    Yield a session bound to a per-test transaction that is always rolled back.

    Each test gets its own connection and outer transaction; the session
    is bound to that connection so every write it makes is undone by the
    rollback in the ``finally`` block, keeping tests isolated from each
    other without recreating the schema per test.

    :param test_engine: Session-scoped engine bound to the test database.
    :return: Async generator yielding one :class:`AsyncSession`.
    """
    async with test_engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest_asyncio.fixture(loop_scope="session")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """
    Yield an ``httpx.AsyncClient`` driving the real app over ASGI.

    Overrides :func:`app.core.database.get_session` so every request the
    client makes reuses the same per-test ``db_session`` (and therefore
    the same rolled-back transaction) instead of opening a connection
    against the real application database.

    :param db_session: The per-test, rolled-back session to inject.
    :return: Async generator yielding one :class:`httpx.AsyncClient`.
    """

    async def _override_get_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client
    app.dependency_overrides.clear()
