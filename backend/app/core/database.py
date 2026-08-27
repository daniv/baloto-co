"""Async SQLAlchemy engine, session factory, and declarative base."""

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncEngine


class Base(DeclarativeBase):
    """Declarative base class shared by every ORM model in the application."""


engine: AsyncEngine = create_async_engine(str(settings.pg_dsn), echo=settings.verbosity > 0)
"""Application-wide async engine, connected to :attr:`settings.pg_dsn`."""

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)
"""Session factory bound to :data:`engine`; use :func:`get_session` to obtain one."""


async def get_session() -> AsyncGenerator[AsyncSession]:
    """
    Yield a request-scoped database session for dependency injection.

    The session commits automatically when the caller completes without
    raising, rolls back on any exception raised by the caller, and is always
    closed afterward so its connection is returned to the pool.

    :return: Asynchronous generator yielding one :class:`AsyncSession`.
    :raises Exception: Re-raises any exception raised by the caller, after
        rolling back the session.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
