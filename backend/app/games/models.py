"""SQLAlchemy ORM models mirroring the pydantic game-draw schemas."""

# date/datetime must stay real (not TYPE_CHECKING-only) imports: SQLAlchemy's
# declarative mapper resolves `Mapped[...]` annotations at class-creation time
# to infer each column's SQL type, so the names must exist at runtime.
from datetime import date, datetime  # noqa: TC003
from typing import Any

from sqlalchemy import BigInteger, SmallInteger, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

type HitTier = dict[str, Any] | None
"""A stored :class:`app.games.schemas.ResultDetails` (``prize_for_winner``/``winners``), or ``None`` if absent."""


class DrawMixin:
    """
    Columns shared by every per-game draw table.

    Mirrors the fields common to every concrete pydantic schema
    (:class:`app.games.schemas.BaseModelSchema` and its subclasses): the
    draw identifier, date, winning numbers, accumulated jackpot, the
    hits-3/4/5 payout tiers, and the derived combination id.
    """

    game_id: Mapped[int] = mapped_column(
        primary_key=True,
        comment="Official draw number ('Sorteo'), unique per game and assigned by the operator.",
    )
    game_date: Mapped[date] = mapped_column(comment="Calendar date the draw was held.")
    numbers: Mapped[list[int]] = mapped_column(
        ARRAY(SmallInteger),
        comment="The 5 winning numbers, ascending and unique, as validated by app.games.schemas.",
    )
    accumulated: Mapped[int] = mapped_column(
        BigInteger,
        comment="Accumulated jackpot for this draw, in Colombian pesos.",
    )
    combination_id: Mapped[str] = mapped_column(
        index=True,
        comment="Hex bitmap identifying the winning-number combination; see app.shared.math_utils.numbers_to_hex.",
    )
    hits_3: Mapped[HitTier] = mapped_column(
        JSONB, comment="3-hits payout tier: {'prize_for_winner': int, 'winners': int}, or null."
    )
    hits_4: Mapped[HitTier] = mapped_column(JSONB, comment="4-hits payout tier.")
    hits_5: Mapped[HitTier] = mapped_column(JSONB, comment="5-hits payout tier.")
    scraped_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        comment="When this row was first inserted by the scraper, not when the draw was held.",
    )


class BalotoRevanchaMixin(DrawMixin):
    """
    Columns shared by Baloto and Revancha, which are drawn from the same balls.

    Baloto and Revancha are independent tables rather than a foreign-key
    relationship. This matches :class:`app.games.schemas.RevanchaSchema`
    extending :class:`app.games.schemas.BalotoSchema` for field reuse only,
    not for a shared row identity — the scraper extracts each game's result
    page independently, so each game keeps its own full row.
    """

    super_balota: Mapped[int] = mapped_column(SmallInteger, comment="The drawn super balota (bonus) number.")
    hits_sb: Mapped[HitTier] = mapped_column(JSONB, comment="Super-balota-only payout tier.")
    hits_2_sb: Mapped[HitTier] = mapped_column(JSONB, comment="2-hits + super-balota payout tier.")
    hits_3_sb: Mapped[HitTier] = mapped_column(JSONB, comment="3-hits + super-balota payout tier.")
    hits_4_sb: Mapped[HitTier] = mapped_column(JSONB, comment="4-hits + super-balota payout tier.")
    hits_5_sb: Mapped[HitTier] = mapped_column(JSONB, comment="5-hits + super-balota payout tier (the jackpot).")


class MilotoDraw(DrawMixin, Base):
    """One persisted Miloto draw result, keyed by its official draw number."""

    __tablename__ = "miloto_draws"

    hits_2: Mapped[HitTier] = mapped_column(JSONB, comment="2-hits payout tier.")


class BalotoDraw(BalotoRevanchaMixin, Base):
    """One persisted Baloto draw result, keyed by its official draw number."""

    __tablename__ = "baloto_draws"


class RevanchaDraw(BalotoRevanchaMixin, Base):
    """One persisted Revancha draw result, keyed by its official draw number."""

    __tablename__ = "revancha_draws"
