"""Persist validated game-draw schemas as SQLAlchemy ORM rows."""

from typing import TYPE_CHECKING

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.games.models import BalotoDraw, MilotoDraw, RevanchaDraw
from app.games.schemas import GameSchema, MilotoSchema, ResultDetails

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

type DrawModel = type[MilotoDraw | BalotoDraw | RevanchaDraw]

_MODEL_BY_GAME: dict[str, DrawModel] = {
    "miloto": MilotoDraw,
    "baloto": BalotoDraw,
    "revancha": RevanchaDraw,
}


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
