"""Per-game HTTP routes: read, scrape-and-save, update, and delete one draw."""

from datetime import date
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import require_admin_api_key
from app.games import repository
from app.games.pagination import PaginatedResponse

# The schema classes must stay real (not TYPE_CHECKING-only) runtime imports:
# FastAPI resolves request-body (``body: MilotoSchema``) and return annotations
# at runtime to build the per-game routes, same constraint as app.games.models.
from app.games.schemas import (
    BalotoSchema,
    GameSchema,
    MilotoDrawListItem,
    MilotoSchema,
    RevanchaSchema,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.games.schemas import Game


# region ROUTERS declarations

miloto_router = APIRouter(prefix="/miloto", tags=["miloto"])
baloto_router = APIRouter(prefix="/baloto", tags=["baloto"])
revancha_router = APIRouter(prefix="/revancha", tags=["revancha"])

# endregion


# region Local Service Functions


def _check_id_match(draw_id: int, body: GameSchema) -> None:
    """
    Reject a body whose ``game_id`` disagrees with the path's ``draw_id``.

    :param draw_id: Draw id taken from the request path.
    :param body: Parsed request body to validate against ``draw_id``.
    :return: None.
    :raises HTTPException: 422 if ``body.game_id`` does not match ``draw_id``.
    """
    if body.game_id != draw_id:
        error_msg = f"Path draw_id {draw_id} does not match body game_id {body.game_id}"
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error_msg)


async def _create_draw(session: AsyncSession, game: Game, draw_id: int, body: GameSchema) -> GameSchema:
    """
    Persist a newly scraped draw, rejecting a mismatched or duplicate id.

    :param session: Async database session.
    :param game: Game the draw belongs to.
    :param draw_id: Draw id taken from the request path.
    :param body: Validated draw payload to store.
    :return: The stored draw, unchanged from ``body``.
    :raises HTTPException: 422 if ``body.game_id`` does not match ``draw_id``; 409 if ``draw_id`` already exists
        or its date collides with another draw of the same game.
    """
    _check_id_match(draw_id, body)

    try:
        await repository.create_draw(session, body)
    except IntegrityError:
        error_message = f"Draw {draw_id} already exists, or its date collides with another {game} draw."
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_message) from None

    return body


async def _replace_draw(session: AsyncSession, game: Game, draw_id: int, body: GameSchema) -> GameSchema:
    """
    Replace an existing stored draw, rejecting a mismatched or missing id.

    :param session: Async database session.
    :param game: Game the draw belongs to.
    :param draw_id: Draw id taken from the request path.
    :param body: Validated replacement draw payload.
    :return: The stored draw, unchanged from ``body``.
    :raises HTTPException: 422 if ``body.game_id`` does not match ``draw_id``; 404 if no draw ``draw_id`` is
        stored; 409 if the updated date collides with another draw of the same game.
    """
    _check_id_match(draw_id, body=body)

    existing = await repository.get_draw(session, game, draw_id)
    if existing is None:
        error_message = f"No {game} with id {draw_id} is stored."
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=error_message)

    try:
        await repository.save_draw(session, body)
    except IntegrityError as error:
        error_message = f"The updated date collides with another {game} draw."
        raise HTTPException(status.HTTP_409_CONFLICT, detail=error_message) from error

    return body


# endregion


# region ROUTERS

# ===============================================================================================================
# Miloto
# ===============================================================================================================


@miloto_router.get("/draws", response_model=PaginatedResponse[MilotoDrawListItem])
async def list_miloto_draws_route(
    session: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 10,
    game_date: Annotated[date | None, Query()] = None,
    jackpot: Annotated[bool | None, Query()] = None,
) -> PaginatedResponse[MilotoDrawListItem]:
    """
    List Miloto draws for a data table, newest first.

    Optionally filtered to a single date or jackpot status.

    :param session: Async database session, injected.
    :param page: 1-indexed page number to return.
    :param size: Number of draws per page, between 1 and 50.
    :param game_date: If given, restrict results to this draw date.
    :param jackpot: If given, restrict results to draws whose jackpot status matches.
    :return: Paginated envelope of Miloto draw list items.
    """
    return await repository.list_miloto_draws(session, page=page, size=size, game_date=game_date, jackpot=jackpot)


@miloto_router.get("/draws/dates", response_model=list[date])
async def list_miloto_draw_dates_route(session: Annotated[AsyncSession, Depends(get_session)]) -> list[date]:
    """
    List every date a Miloto draw was held, for restricting a date-picker to valid draw dates.

    :param session: Async database session, injected.
    :return: Every distinct Miloto draw date, in the order returned by the repository.
    """
    return await repository.list_miloto_draw_dates(session)


@miloto_router.get("/draw/{draw_id}")
async def get_miloto_draw_route(draw_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> GameSchema:
    """
    Fetch a single Miloto draw by its draw id.

    :param draw_id: Draw id to look up.
    :param session: Async database session, injected.
    :return: The stored Miloto draw.
    :raises HTTPException: 404 if no Miloto draw ``draw_id`` is stored.
    """
    result = await repository.get_draw(session, game="miloto", draw_id=draw_id)

    if result is None:
        error_message = f"No miloto game id {draw_id} is stored."
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=error_message)

    return result


@miloto_router.post("/draw/{draw_id}", dependencies=[Depends(require_admin_api_key)])
async def add_miloto_draw_route(
    draw_id: int, body: MilotoSchema, session: Annotated[AsyncSession, Depends(get_session)]
) -> GameSchema:
    """
    Scrape the live Miloto result for ``draw_id`` and store it.

    :param draw_id: Draw id to scrape and store.
    :param body: Client-supplied draw payload, validated against ``draw_id``.
    :param session: Async database session, injected.
    :return: The stored Miloto draw.
    :raises HTTPException: 422 if ``body.game_id`` does not match ``draw_id``; 409 if ``draw_id`` already
        exists or its date collides with another Miloto draw.
    """
    return await _create_draw(session, "miloto", draw_id=draw_id, body=body)


@miloto_router.patch("/draw/{draw_id}", dependencies=[Depends(require_admin_api_key)])
async def update_miloto_draw_route(
    draw_id: int, body: MilotoSchema, session: Annotated[AsyncSession, Depends(get_session)]
) -> GameSchema:
    """
    Replace the stored Miloto draw ``draw_id`` with ``body``.

    :param draw_id: Draw id to replace.
    :param body: Replacement draw payload, validated against ``draw_id``.
    :param session: Async database session, injected.
    :return: The stored Miloto draw.
    :raises HTTPException: 422 if ``body.game_id`` does not match ``draw_id``; 404 if no Miloto draw
        ``draw_id`` is stored; 409 if the updated date collides with another Miloto draw.
    """
    return await _replace_draw(session, "miloto", draw_id, body)


@miloto_router.delete(
    "/draw/{draw_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin_api_key)]
)
async def delete_miloto_draw_route(draw_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> None:
    """
    Delete the stored Miloto draw ``draw_id``.

    :param draw_id: Draw id to delete.
    :param session: Async database session, injected.
    :return: None.
    :raises HTTPException: 404 if no Miloto draw ``draw_id`` is stored.
    """
    deleted = await repository.delete_draw(session, "miloto", draw_id)

    if not deleted:
        error_message = f"No miloto game id {draw_id} is stored"
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=error_message)


# ===============================================================================================================
# Baloto
# ===============================================================================================================


@baloto_router.get("/draw/{draw_id}")
async def get_baloto_draw_route(draw_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> GameSchema:
    """
    Fetch a single Baloto draw by its draw id.

    :param draw_id: Draw id to look up.
    :param session: Async database session, injected.
    :return: The stored Baloto draw.
    :raises HTTPException: 404 if no Baloto draw ``draw_id`` is stored.
    """
    result = await repository.get_draw(session, game="baloto", draw_id=draw_id)

    if result is None:
        error_message = f"No baloto game id {draw_id} is stored."
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=error_message)

    return result


@baloto_router.post("/draw/{draw_id}", dependencies=[Depends(require_admin_api_key)])
async def add_baloto_draw_route(
    draw_id: int, body: BalotoSchema, session: Annotated[AsyncSession, Depends(get_session)]
) -> GameSchema:
    """
    Scrape the live Baloto result for ``draw_id`` and store it.

    :param draw_id: Draw id to scrape and store.
    :param body: Client-supplied draw payload, validated against ``draw_id``.
    :param session: Async database session, injected.
    :return: The stored Baloto draw.
    :raises HTTPException: 422 if ``body.game_id`` does not match ``draw_id``; 409 if ``draw_id`` already
        exists or its date collides with another Baloto draw.
    """
    return await _create_draw(session, "baloto", draw_id=draw_id, body=body)


@baloto_router.patch("/draw/{draw_id}", dependencies=[Depends(require_admin_api_key)])
async def update_baloto_draw_route(
    draw_id: int, body: BalotoSchema, session: Annotated[AsyncSession, Depends(get_session)]
) -> GameSchema:
    """
    Replace the stored Baloto draw ``draw_id`` with ``body``.

    :param draw_id: Draw id to replace.
    :param body: Replacement draw payload, validated against ``draw_id``.
    :param session: Async database session, injected.
    :return: The stored Baloto draw.
    :raises HTTPException: 422 if ``body.game_id`` does not match ``draw_id``; 404 if no Baloto draw
        ``draw_id`` is stored; 409 if the updated date collides with another Baloto draw.
    """
    return await _replace_draw(session, "baloto", draw_id, body)


@baloto_router.delete(
    "/draw/{draw_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin_api_key)]
)
async def delete_baloto_draw_route(draw_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> None:
    """
    Delete the stored Baloto draw ``draw_id``.

    :param draw_id: Draw id to delete.
    :param session: Async database session, injected.
    :return: None.
    :raises HTTPException: 404 if no Baloto draw ``draw_id`` is stored.
    """
    deleted = await repository.delete_draw(session, "baloto", draw_id)

    if not deleted:
        error_message = f"No baloto game id {draw_id} is stored"
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=error_message)


# ===============================================================================================================
# Revancha
# ===============================================================================================================


@revancha_router.get("/draw/{draw_id}")
async def get_revancha_draw_route(draw_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> GameSchema:
    """
    Fetch a single Revancha draw by its draw id.

    :param draw_id: Draw id to look up.
    :param session: Async database session, injected.
    :return: The stored Revancha draw.
    :raises HTTPException: 404 if no Revancha draw ``draw_id`` is stored.
    """
    result = await repository.get_draw(session, game="revancha", draw_id=draw_id)

    if result is None:
        error_message = f"No revancha game id {draw_id} is stored."
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=error_message)

    return result


@revancha_router.post("/draw/{draw_id}", dependencies=[Depends(require_admin_api_key)])
async def add_revancha_draw_route(
    draw_id: int, body: RevanchaSchema, session: Annotated[AsyncSession, Depends(get_session)]
) -> GameSchema:
    """
    Scrape the live Revancha result for ``draw_id`` and store it.

    :param draw_id: Draw id to scrape and store.
    :param body: Client-supplied draw payload, validated against ``draw_id``.
    :param session: Async database session, injected.
    :return: The stored Revancha draw.
    :raises HTTPException: 422 if ``body.game_id`` does not match ``draw_id``; 409 if ``draw_id`` already
        exists or its date collides with another Revancha draw.
    """
    return await _create_draw(session, "revancha", draw_id=draw_id, body=body)


@revancha_router.patch("/draw/{draw_id}", dependencies=[Depends(require_admin_api_key)])
async def update_revancha_draw_route(
    draw_id: int, body: RevanchaSchema, session: Annotated[AsyncSession, Depends(get_session)]
) -> GameSchema:
    """
    Replace the stored Revancha draw ``draw_id`` with ``body``.

    :param draw_id: Draw id to replace.
    :param body: Replacement draw payload, validated against ``draw_id``.
    :param session: Async database session, injected.
    :return: The stored Revancha draw.
    :raises HTTPException: 422 if ``body.game_id`` does not match ``draw_id``; 404 if no Revancha draw
        ``draw_id`` is stored; 409 if the updated date collides with another Revancha draw.
    """
    return await _replace_draw(session, "revancha", draw_id, body)


@revancha_router.delete(
    "/draw/{draw_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin_api_key)]
)
async def delete_revancha_draw_route(draw_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> None:
    """
    Delete the stored Revancha draw ``draw_id``.

    :param draw_id: Draw id to delete.
    :param session: Async database session, injected.
    :return: None.
    :raises HTTPException: 404 if no Revancha draw ``draw_id`` is stored.
    """
    deleted = await repository.delete_draw(session, "revancha", draw_id)

    if not deleted:
        error_message = f"No revancha game id {draw_id} is stored"
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=error_message)


# endregion
