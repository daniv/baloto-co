"""FastAPI application entrypoint: the app instance and its lifespan."""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI

from app.core.config import settings
from app.games.router import build_game_router
from app.scraper.playwright_client import PlaywrightClient

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """
    Manage resources shared for the lifetime of the running application.

    Starts the shared :class:`~app.scraper.playwright_client.PlaywrightClient`
    on startup and stores it on ``app.state`` for
    :func:`~app.scraper.playwright_client.get_page` to reach, then closes it
    on shutdown. The database engine needs no equivalent step here: it is
    already created eagerly at import time, in :mod:`app.core.database`.

    :param app: The FastAPI application instance being started.
    :return: Asynchronous generator yielding control back to FastAPI while the app runs.
    """
    async with PlaywrightClient() as playwright_client:
        app.state.playwright_client = playwright_client
        yield


app = FastAPI(
    title=settings.name,
    version=settings.version,
    description=settings.description,
    lifespan=lifespan,
)

for game in ("miloto", "baloto", "revancha"):
    app.include_router(build_game_router(game))
