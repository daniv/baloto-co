"""
Async httpx client fixture for the game API integration test suite.

Binds an ``httpx.AsyncClient`` to the FastAPI app over an ASGI transport so the
write/read routes run against a real Postgres instance (the one configured via
the repo-root ``.env`` and consumed by ``app.core.config.settings``). All
``http_client`` calls flow through the app's own dependency graph
(``get_session`` -> ``async_session_factory`` -> ``settings.pg_dsn``), so
persistence is exercised against the actual database rather than a mock.

The fixture is deliberately **non-destructive**: it never truncates or drops a
table, and it never removes rows that pre-existed the test run. A session
fixture calls ``Base.metadata.create_all`` (which only creates tables that do
not exist yet), and a per-test fixture snapshots the set of ``game_id`` rows in
each game table before the test so it can delete exactly the rows the test
created on teardown, leaving any pre-existing draw data untouched.
"""

from typing import TYPE_CHECKING

import httpx
import pytest
import pytest_asyncio
from app.core.database import Base, async_session_factory, engine
from app.main import app
from httpx import ASGITransport
from sqlalchemy import Table, delete, select

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

GAME_TABLES: tuple[str, ...] = ("miloto_draws", "baloto_draws", "revancha_draws")
RESERVED_TEST_GAME_ID = 100_000_000


@pytest.fixture
def miloto_payload() -> dict[str, object]:
    """
    Return a validated Miloto draw request body keyed to the reserved test id.

    The body is built in code with ``game_id`` set to ``RESERVED_TEST_GAME_ID``
    so the path and payload always agree, and carries the prize-tier values of a
    realistic Miloto draw so the write route's validation and persistence can be
    exercised end to end.

    :return: The Miloto draw payload to POST to ``/miloto/draw/{RESERVED_TEST_GAME_ID}``.
    """
    return {
        "game": "miloto",
        "game_id": RESERVED_TEST_GAME_ID,
        "game_date": "2024-02-05",
        "numbers": [4, 18, 26, 31, 39],
        "accumulated": 150_000_000,
        "hits_2": {"prize_for_winner": 4_000, "winners": 4_513},
        "hits_3": {"prize_for_winner": 45_050, "winners": 432},
        "hits_4": {"prize_for_winner": 849_400, "winners": 13},
        "hits_5": None,
    }


@pytest_asyncio.fixture(scope="session")
async def sync_schema() -> AsyncGenerator[None]:
    """
    Create any missing ORM tables on the configured Postgres database.

    ``create_all`` only emits ``CREATE TABLE`` for tables that do not yet
    exist; it never drops, alters, or truncates existing tables, so this is a
    no-op against an already-migrated database and never touches data.

    :return: Asynchronous generator that yields once after provisioning.
    """
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture(autouse=True)
async def release_reserved_test_id(sync_schema: None) -> AsyncGenerator[None]:
    """
    Clear the reserved test id from every game table before each test.

    Deleting ``RESERVED_TEST_GAME_ID`` up front guarantees a ``POST`` to
    ``/{game}/draw/{RESERVED_TEST_GAME_ID}`` returns 200 (never a 409 duplicate)
    and that any ``GET`` expecting 404 stays deterministic, while the
    ``remove_test_created_rows`` diff re-removes the row after the test.

    :param sync_schema: Ensures the tables exist before deletion.
    :return: Asynchronous generator that releases the id before each test.
    """
    for table in GAME_TABLES:
        await _delete_rows(table, {RESERVED_TEST_GAME_ID})
    yield


@pytest_asyncio.fixture(autouse=True)
async def remove_test_created_rows(sync_schema: None) -> AsyncGenerator[None]:
    """
    Delete only the game rows a test inserted, leaving pre-existing data intact.

    Snapshots the set of ``game_id`` values present in each game table before
    the test, then on teardown deletes exactly the ``game_id`` values that were
    not in that baseline. Rows that existed before the test are never touched.

    :param sync_schema: Ensures the tables exist before snapshotting.
    :return: Asynchronous generator that restores the baseline on teardown.
    """
    baseline = await _collect_game_ids()
    yield
    created = await _collect_game_ids()
    for table in GAME_TABLES:
        new_ids = created[table] - baseline[table]
        if new_ids:
            await _delete_rows(table, new_ids)


@pytest_asyncio.fixture
async def http_client(sync_schema: None) -> AsyncGenerator[httpx.AsyncClient]:
    """
    Provide an async httpx client bound to the FastAPI app over an ASGI transport.

    The client sends requests directly into ``app.main:app`` without opening a
    real socket or subprocess, while every dependency it resolves still talks
    to the real Postgres instance. Yielded for the whole session and always
    closed afterwards.

    :param sync_schema: Guarantees the database schema is provisioned.
    :return: Asynchronous generator yielding one ``httpx.AsyncClient``.
    """
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


def _table_for(name: str) -> Table:
    """Return the SQLAlchemy Core ``Table`` for the given game table name."""
    return Base.metadata.tables[name]


async def _collect_game_ids() -> dict[str, set[int]]:
    """Return the set of ``game_id`` values currently stored in every game table."""
    ids: dict[str, set[int]] = {table: set() for table in GAME_TABLES}
    async with async_session_factory() as session:
        for table in GAME_TABLES:
            table_obj = _table_for(table)
            result = await session.execute(select(table_obj.c.game_id))
            ids[table] = {row[0] for row in result}
    return ids


async def _delete_rows(table: str, game_ids: set[int]) -> None:
    """Delete the given rows from ``table`` by primary-key ``game_id``."""
    table_obj = _table_for(table)
    async with async_session_factory() as session:
        for game_id in game_ids:
            stmt = delete(table_obj).where(table_obj.c.game_id == game_id)
            await session.execute(stmt)
        await session.commit()
