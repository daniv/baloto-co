"""Persist validated game-draw schemas as SQLAlchemy ORM rows."""

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import func, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.games.models import BalotoDraw, MilotoDraw, RevanchaDraw
from app.games.pagination import PaginatedResponse
from app.games.schemas import (
    BalotoSchema,
    Game,
    GameSchema,
    MilotoDrawListItem,
    MilotoSchema,
    ResultDetails,
    RevanchaSchema,
)
from app.shared.date_utils import full_date
from app.shared.math_utils import abbreviate_pesos

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

type DrawModel = type[MilotoDraw | BalotoDraw | RevanchaDraw]
type DrawRow = MilotoDraw | BalotoDraw | RevanchaDraw

_MODEL_BY_GAME: dict[Game, DrawModel] = {
    "miloto": MilotoDraw,
    "baloto": BalotoDraw,
    "revancha": RevanchaDraw,
}


def _to_list_item(row: MilotoDraw) -> MilotoDrawListItem:
    """Map one ``miloto_draws`` row to the lightweight table projection."""
    return MilotoDrawListItem(
        game_id=row.game_id,
        game_date=full_date(row.game_date),
        numbers=row.numbers,
        accumulated=abbreviate_pesos(row.accumulated),
        jackpot=row.hits_5 is not None,
    )


def _hits_payload(details: ResultDetails | None) -> dict[str, int] | None:
    """Serialize a ``ResultDetails`` field to the dict stored in a JSONB column."""
    return details.model_dump() if details is not None else None


def _draw_values(result: GameSchema) -> dict[str, object]:
    """Map one validated schema to the column values for its matching draw table."""
    values: dict[str, object] = {
        "game_id": result.game_id,
        "game_date": result.game_date,
        "numbers": result.numbers,
        "accumulated": result.accumulated,
        "combination_id": result.combination_id,
        "hits_3": _hits_payload(result.hits_3),
        "hits_4": _hits_payload(result.hits_4),
        "hits_5": _hits_payload(result.hits_5),
    }

    if isinstance(result, MilotoSchema):
        values["hits_2"] = _hits_payload(result.hits_2)
    else:
        values["super_balota"] = result.super_balota
        values["hits_sb"] = _hits_payload(result.hits_sb)
        values["hits_2_sb"] = _hits_payload(result.hits_2_sb)
        values["hits_3_sb"] = _hits_payload(result.hits_3_sb)
        values["hits_4_sb"] = _hits_payload(result.hits_4_sb)
        values["hits_5_sb"] = _hits_payload(result.hits_5_sb)

    return values


async def create_draw(session: AsyncSession, result: GameSchema) -> None:
    """
    Insert one validated draw result; fails if it already exists.

    Unlike :func:`save_draw`, this issues a plain ``INSERT`` with no
    upsert fallback, so creating an already-stored ``game_id`` raises
    :class:`sqlalchemy.exc.IntegrityError` (primary-key violation)
    instead of silently overwriting it — corrections to an existing draw
    should go through :func:`update_draw` instead. The same exception
    type is raised if ``game_date`` collides with a different existing
    draw, since ``game_date`` is unique per game.

    :param session: Active session used to execute the statement. The caller
        owns the transaction and is responsible for committing or rolling
        back (see :func:`app.core.database.get_session`).
    :param result: Validated draw result to persist.
    :return: None.
    :raises sqlalchemy.exc.IntegrityError: If ``game_id`` or ``game_date`` collides
        with an already-stored draw.
    """
    model = _MODEL_BY_GAME[result.game]
    values = _draw_values(result)

    await session.execute(insert(model).values(**values))


async def save_draw(session: AsyncSession, result: GameSchema) -> None:
    """
    Insert one validated draw result, or update it if already stored.

    The destination table is chosen from ``result.game``
    (:class:`~app.games.models.MilotoDraw`, :class:`~app.games.models.BalotoDraw`,
    or :class:`~app.games.models.RevanchaDraw`). The statement is a single
    atomic ``INSERT ... ON CONFLICT (game_id) DO UPDATE``, so re-scraping and
    re-saving an already-stored draw overwrites every column except the
    primary key instead of failing or creating a duplicate row.

    :param session: Active session used to execute the statement. The caller
        owns the transaction and is responsible for committing or rolling
        back (see :func:`app.core.database.get_session`).
    :param result: Validated draw result to persist.
    :return: None.
    """
    model = _MODEL_BY_GAME[result.game]
    values = _draw_values(result)
    update_columns = {key: value for key, value in values.items() if key != "game_id"}

    statement = pg_insert(model).values(**values)
    statement = statement.on_conflict_do_update(index_elements=["game_id"], set_=update_columns)

    await session.execute(statement)


def _hit_tier_from_row(payload: dict[str, int] | None) -> ResultDetails | None:
    """Deserialize a JSONB payout-tier column back into a ``ResultDetails``."""
    return ResultDetails(**payload) if payload is not None else None


def _to_schema(row: DrawRow) -> GameSchema:
    """Convert one persisted draw row back into its validated pydantic schema."""
    if isinstance(row, MilotoDraw):
        return MilotoSchema(
            game_id=row.game_id,
            game_date=row.game_date,
            numbers=row.numbers,
            accumulated=row.accumulated,
            hits_3=_hit_tier_from_row(row.hits_3),
            hits_4=_hit_tier_from_row(row.hits_4),
            hits_5=_hit_tier_from_row(row.hits_5),
            hits_2=_hit_tier_from_row(row.hits_2),
        )

    schema_class = BalotoSchema if isinstance(row, BalotoDraw) else RevanchaSchema
    return schema_class(
        game_id=row.game_id,
        game_date=row.game_date,
        numbers=row.numbers,
        accumulated=row.accumulated,
        hits_3=_hit_tier_from_row(row.hits_3),
        hits_4=_hit_tier_from_row(row.hits_4),
        hits_5=_hit_tier_from_row(row.hits_5),
        super_balota=row.super_balota,
        hits_sb=_hit_tier_from_row(row.hits_sb),
        hits_2_sb=_hit_tier_from_row(row.hits_2_sb),
        hits_3_sb=_hit_tier_from_row(row.hits_3_sb),
        hits_4_sb=_hit_tier_from_row(row.hits_4_sb),
        hits_5_sb=_hit_tier_from_row(row.hits_5_sb),
    )


async def get_draw(session: AsyncSession, game: Game, draw_id: int) -> GameSchema | None:
    """
    Fetch one persisted draw and convert it back into its validated schema.

    :param session: Active session used to execute the query.
    :param game: Which per-game table to query.
    :param draw_id: The draw's official number (``game_id``, the table's primary key).
    :return: The matching validated schema, or ``None`` if no such draw is stored.
    """
    model = _MODEL_BY_GAME[game]
    row = await session.get(model, draw_id)

    return _to_schema(row) if row is not None else None


def _rebuild_with_updates(current: GameSchema, updates: dict[str, object]) -> GameSchema:
    """Re-validate one schema instance with a partial field update merged in."""
    data = current.model_dump(exclude={"combination_id"})
    data.update(updates)
    return type(current)(**data)


async def update_draw(session: AsyncSession, game: Game, draw_id: int, updates: dict[str, object]) -> GameSchema | None:
    """
    Apply a partial update to one persisted draw, re-validating the full result.

    Every field present in ``updates`` replaces the stored value; every
    field left out keeps its current value. The merged result is
    re-validated through the schema's normal constructor rather than a
    bypassed shallow copy, so existing invariants (unique/sorted numbers,
    jackpot floors, no future dates) still apply to a partially corrected
    draw.

    :param session: Active session used to execute the read and the upsert.
    :param game: Which per-game table to update.
    :param draw_id: The draw's official number (``game_id``, the table's primary key).
    :param updates: Mapping of field name to new value; fields left out are unchanged.
    :return: The updated, re-validated schema, or ``None`` if no such draw is stored.
    :raises pydantic.ValidationError: If the merged field values violate the schema's constraints.
    """
    current = await get_draw(session, game, draw_id)

    if current is None:
        return None

    updated = _rebuild_with_updates(current, updates)
    await save_draw(session, updated)
    return updated


async def delete_draw(session: AsyncSession, game: Game, draw_id: int) -> bool:
    """
    Delete one persisted draw by its official draw number.

    :param session: Active session used to execute the statement. The caller
        owns the transaction and is responsible for committing or rolling
        back (see :func:`app.core.database.get_session`).
    :param game: Which per-game table to delete from.
    :param draw_id: The draw's official number (``game_id``, the table's primary key).
    :return: ``True`` if a row was deleted, ``False`` if no matching draw was stored.
    """
    model = _MODEL_BY_GAME[game]
    row = await session.get(model, draw_id)

    if row is None:
        return False

    await session.delete(row)
    return True


async def list_miloto_draws(
    session: AsyncSession,
    page: int,
    size: int,
    game_date: date | None = None,
    *,
    jackpot: bool | None = None,
) -> PaginatedResponse[MilotoDrawListItem]:
    """
    Fetch a page of Miloto draws for a frontend data table, newest first.

    Returns a lightweight projection (``MilotoDrawListItem``) of at most
    ``size`` rows ordered by ``game_id`` descending. When ``total`` is zero
    the ``pages`` count is 0.

    :param session: Active session used to run the queries.
    :param page: 1-indexed page number (>= 1).
    :param size: Number of items per page (1..20).
    :param game_date: When given, restrict the result to the single draw held on this date.
    :param jackpot: When ``True``, only rows where the jackpot was hit (``hits_5`` holds actual
                    payout data). When ``False``, only rows where the jackpot was not hit.
                    ``hits_5`` is a JSONB column, so jackpot-hit rows are those whose JSON value
                    is not the JSON literal ``null`` (checked via ``jsonb_typeof``), not rows that
                    are SQL ``NULL``.
    :return: A paginated envelope of table rows.
    """
    model = MilotoDraw
    count_stmt = select(func.count()).select_from(model)
    query_stmt = select(model).order_by(model.game_id.desc())

    if game_date is not None:
        count_stmt = count_stmt.where(model.game_date == game_date)
        query_stmt = query_stmt.where(model.game_date == game_date)

    if jackpot is True:
        count_stmt = count_stmt.where(func.jsonb_typeof(model.hits_5) != "null")
        query_stmt = query_stmt.where(func.jsonb_typeof(model.hits_5) != "null")
    elif jackpot is False:
        count_stmt = count_stmt.where(func.jsonb_typeof(model.hits_5) == "null")
        query_stmt = query_stmt.where(func.jsonb_typeof(model.hits_5) == "null")

    total = (await session.execute(count_stmt)).scalar_one()
    result = await session.execute(query_stmt.offset((page - 1) * size).limit(size))
    items = [_to_list_item(row) for row in result.scalars()]

    pages = 0 if total == 0 else (total + size - 1) // size
    return PaginatedResponse[MilotoDrawListItem](items=items, page=page, size=size, total=total, pages=pages)


async def list_miloto_draw_dates(session: AsyncSession) -> list[date]:
    """Return every calendar date a Miloto draw is stored for, ascending — used to restrict a date picker."""
    result = await session.execute(select(MilotoDraw.game_date).order_by(MilotoDraw.game_date))
    return list(result.scalars())
