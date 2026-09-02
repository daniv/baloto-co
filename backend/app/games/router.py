"""Per-game HTTP routes: read, scrape-and-save, update, and delete one draw."""

from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import require_admin_api_key
from app.games import repository
from app.games.schemas import (
    BalotoSchema,
    GameSchema,
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
    """Reject a body whose ``game_id`` disagrees with the path's ``draw_id``."""
    if body.game_id != draw_id:
        error_msg = f"Path draw_id {draw_id} does not match body game_id {body.game_id}"
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error_msg)


async def _create_draw(session: AsyncSession, game: Game, draw_id: int, body: GameSchema) -> GameSchema:
    _check_id_match(draw_id, body)

    try:
        await repository.create_draw(session, body)
    except IntegrityError:
        error_message = f"Draw {draw_id} already exists, or its date collides with another {geme} draw."
        raise HTTPException(status_code=status.HTTP_400_CONFLICT, detail=error_message)

    return body


async def _replace_draw(session: AsyncSession, game: Game, draw_id: int, body: GameSchema) -> GameSchema:
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

@miloto_router.get("/draw/{draw_id}")
async def get_miloto_draw_route(draw_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> GameSchema:
    result = await repository.get_draw(session, game="miloto", draw_id=draw_id)

    if result is None:
        error_message = f"No miloto game id {draw_id} is stored."
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=error_message)

    return result


@miloto_router.post("/draw/{draw_id}", dependencies=[Depends(require_admin_api_key)])
async def add_miloto_draw_route(
    draw_id: int, 
    body: MilotoSchema,
    session: Annotated[AsyncSession, Depends(get_session)]
) -> GameSchema:
    return await _create_draw(session, "miloto", draw_id=draw_id, body=body)


@miloto_router.patch("/draw/{draw_id}", dependencies=[Depends(require_admin_api_key)])
async def update_miloto_draw_route(
    draw_id: int, 
    body: MilotoSchema,
    session: Annotated[AsyncSession, Depends(get_session)]
) -> GameSchema:
    return await _replace_draw(session, "miloto", draw_id, body)


@miloto_router.delete(
        "/draw/{draw_id}", 
        status_code=status.HTTP_204_NO_CONTENT, 
        dependencies=[Depends(require_admin_api_key)]
)
async def delete_miloto_draw_route(draw_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> None:
    deleted = await repository.delete_draw(session, "miloto", draw_id)

    if not deleted:
        error_message = f"No miloto game id {draw_id} is stored"
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=error_message)


# ===============================================================================================================
# Baloto
# ===============================================================================================================

@baloto_router.get("/draw/{draw_id}")
async def get_baloto_draw_route(draw_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> GameSchema:
    result = await repository.get_draw(session, game="baloto", draw_id=draw_id)

    if result is None:
        error_message = f"No baloto game id {draw_id} is stored."
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=error_message)

    return result


@baloto_router.post("/draw/{draw_id}", dependencies=[Depends(require_admin_api_key)])
async def add_baloto_draw_route(
    draw_id: int, 
    body: BalotoSchema,
    session: Annotated[AsyncSession, Depends(get_session)]
) -> GameSchema:
    return await _create_draw(session, "baloto", draw_id=draw_id, body=body)


@baloto_router.patch("/draw/{draw_id}", dependencies=[Depends(require_admin_api_key)])
async def update_baloto_draw_route(
    draw_id: int, 
    body: BalotoSchema,
    session: Annotated[AsyncSession, Depends(get_session)]
) -> GameSchema:
    return await _replace_draw(session, "baloto", draw_id, body)


@baloto_router.delete(
        "/draw/{draw_id}", 
        status_code=status.HTTP_204_NO_CONTENT, 
        dependencies=[Depends(require_admin_api_key)]
)
async def delete_baloto_draw_route(draw_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> None:
    deleted = await repository.delete_draw(session, "baloto", draw_id)

    if not deleted:
        error_message = f"No baloto game id {draw_id} is stored"
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=error_message)


# ===============================================================================================================
# Revancha
# ===============================================================================================================

@revancha_router.get("/draw/{draw_id}")
async def get_revancha_draw_route(draw_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> GameSchema:
    result = await repository.get_draw(session, game="revancha", draw_id=draw_id)

    if result is None:
        error_message = f"No revancha game id {draw_id} is stored."
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=error_message)

    return result


@revancha_router.post("/draw/{draw_id}", dependencies=[Depends(require_admin_api_key)])
async def add_revancha_draw_route(
    draw_id: int, 
    body: RevanchaSchema,
    session: Annotated[AsyncSession, Depends(get_session)]
) -> GameSchema:
    return await _create_draw(session, "revancha", draw_id=draw_id, body=body)


@revancha_router.patch("/draw/{draw_id}", dependencies=[Depends(require_admin_api_key)])
async def update_revancha_draw_route(
    draw_id: int, 
    body: RevanchaSchema,
    session: Annotated[AsyncSession, Depends(get_session)]
) -> GameSchema:
    return await _replace_draw(session, "revancha", draw_id, body)


@revancha_router.delete(
        "/draw/{draw_id}", 
        status_code=status.HTTP_204_NO_CONTENT, 
        dependencies=[Depends(require_admin_api_key)]
)
async def delete_revancha_draw_route(draw_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> None:
    deleted = await repository.delete_draw(session, "baloto", draw_id)

    if not deleted:
        error_message = f"No revancha game id {draw_id} is stored"
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=error_message)

# endregion
