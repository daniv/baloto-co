"""Per-game HTTP routes: read, scrape-and-save, update, and delete one draw."""

# datetime must stay a real (not TYPE_CHECKING-only) import: pydantic's BaseModel
# resolves field annotations at class-creation time to build its validators, so
# the name must exist at runtime -- same constraint as app.games.models.
import datetime  # noqa: TC003
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy.exc import IntegrityError

from app.core.database import get_session
from app.core.security import require_admin_api_key
from app.games import repository
from app.games.schemas import (  # noqa: TC001 -- used as route request/return types FastAPI resolves at runtime
    BalotoRevanchaNumbers,
    GameSchema,
    MilotoNumbers,
    ResultDetails,
)
from app.games.scrape_service import scrape_draw
from app.scraper import DrawPageNotFoundError
from app.scraper.playwright_client import get_page

if TYPE_CHECKING:
    from playwright.async_api import Page
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.games.schemas import Game


class MilotoDrawUpdate(BaseModel):
    """Partial update for one Miloto draw; fields left unset are unchanged."""

    model_config = ConfigDict(extra="forbid")

    game_date: datetime.date | None = None
    numbers: MilotoNumbers | None = None
    accumulated: int | None = None
    hits_2: ResultDetails | None = None
    hits_3: ResultDetails | None = None
    hits_4: ResultDetails | None = None
    hits_5: ResultDetails | None = None


class BalotoRevanchaDrawUpdate(BaseModel):
    """Partial update for one Baloto or Revancha draw; fields left unset are unchanged."""

    model_config = ConfigDict(extra="forbid")

    game_date: datetime.date | None = None
    numbers: BalotoRevanchaNumbers | None = None
    accumulated: int | None = None
    super_balota: int | None = None
    hits_3: ResultDetails | None = None
    hits_4: ResultDetails | None = None
    hits_5: ResultDetails | None = None
    hits_sb: ResultDetails | None = None
    hits_2_sb: ResultDetails | None = None
    hits_3_sb: ResultDetails | None = None
    hits_4_sb: ResultDetails | None = None
    hits_5_sb: ResultDetails | None = None


def _register_get_route(router: APIRouter, game: Game) -> None:
    """Register the public ``GET /draw/{draw_id}`` route on ``router``."""

    @router.get("/draw/{draw_id}")
    async def get_draw_route(  # pyright: ignore[reportUnusedFunction] -- registered on router via the decorator
        draw_id: int,
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> GameSchema:
        """Return one persisted draw."""
        result = await repository.get_draw(session, game, draw_id)

        if result is None:
            error_message = f"No {game} draw {draw_id} is stored."
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_message)

        return result


def _register_post_route(router: APIRouter, game: Game) -> None:
    """Register the admin-gated ``POST /draw/{draw_id}`` (scrape-and-save) route on ``router``."""

    @router.post("/draw/{draw_id}", dependencies=[Depends(require_admin_api_key)])
    async def add_draw_route(  # pyright: ignore[reportUnusedFunction] -- registered on router via the decorator
        draw_id: int,
        session: Annotated[AsyncSession, Depends(get_session)],
        page: Annotated[Page, Depends(get_page)],
    ) -> GameSchema:
        """Scrape one live draw result page and persist it. Requires the admin API key."""
        try:
            result = await scrape_draw(page, game, draw_id)
        except DrawPageNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except ValidationError as error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
        except (AssertionError, ValueError, RuntimeError) as error:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error

        try:
            await repository.create_draw(session, result)
        except IntegrityError as error:
            error_message = f"Draw {draw_id} already exists, or its date collides with another {game} draw."
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_message) from error

        return result


async def _apply_update(session: AsyncSession, game: Game, draw_id: int, updates: dict[str, object]) -> GameSchema:
    """Apply a validated partial update through the repository, or raise the matching HTTP error."""
    try:
        result = await repository.update_draw(session, game, draw_id, updates)
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    except IntegrityError as error:
        error_message = f"The updated date collides with another {game} draw."
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_message) from error

    if result is None:
        error_message = f"No {game} draw {draw_id} is stored."
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_message)

    return result


def _register_patch_route(router: APIRouter, game: Game) -> None:
    """Register the admin-gated ``PATCH /draw/{draw_id}`` (partial update) route on ``router``."""
    if game == "miloto":

        @router.patch("/draw/{draw_id}", dependencies=[Depends(require_admin_api_key)])
        async def update_miloto_draw_route(  # pyright: ignore[reportUnusedFunction] -- registered via the decorator
            draw_id: int,
            body: MilotoDrawUpdate,
            session: Annotated[AsyncSession, Depends(get_session)],
        ) -> GameSchema:
            """Apply a partial update to one persisted Miloto draw. Requires the admin API key."""
            return await _apply_update(session, game, draw_id, body.model_dump(exclude_unset=True))
    else:

        @router.patch("/draw/{draw_id}", dependencies=[Depends(require_admin_api_key)])
        async def update_baloto_revancha_draw_route(  # pyright: ignore[reportUnusedFunction] -- registered via decorator
            draw_id: int,
            body: BalotoRevanchaDrawUpdate,
            session: Annotated[AsyncSession, Depends(get_session)],
        ) -> GameSchema:
            """Apply a partial update to one persisted draw. Requires the admin API key."""
            return await _apply_update(session, game, draw_id, body.model_dump(exclude_unset=True))


def _register_delete_route(router: APIRouter, game: Game) -> None:
    """Register the admin-gated ``DELETE /draw/{draw_id}`` route on ``router``."""

    @router.delete(
        "/draw/{draw_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[Depends(require_admin_api_key)],
    )
    async def delete_draw_route(  # pyright: ignore[reportUnusedFunction] -- registered on router via the decorator
        draw_id: int,
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> None:
        """Delete one persisted draw. Requires the admin API key."""
        deleted = await repository.delete_draw(session, game, draw_id)

        if not deleted:
            error_message = f"No {game} draw {draw_id} is stored."
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_message)


def build_game_router(game: Game) -> APIRouter:
    """
    Build the read/write/update/delete draw routes for one game.

    Called once per game (see :mod:`app.main`) to mount the same four
    routes at ``/miloto``, ``/baloto``, and ``/revancha`` — one shared
    implementation instead of quadrupling identical route bodies. Reads
    are public; writing, updating, and deleting require
    :func:`~app.core.security.require_admin_api_key`.

    :param game: Which game this router serves.
    :return: A configured :class:`~fastapi.APIRouter` with four routes.
    """
    router = APIRouter(prefix=f"/{game}", tags=[game])
    _register_get_route(router, game)
    _register_post_route(router, game)
    _register_patch_route(router, game)
    _register_delete_route(router, game)
    return router
