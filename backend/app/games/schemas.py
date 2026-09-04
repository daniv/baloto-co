"""Pydantic schemas for lottery game draw results."""

import datetime
from abc import ABC, abstractmethod
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, computed_field, field_validator

from app.core.config import settings
from app.shared.date_utils import parse_spanish_date
from app.shared.math_utils import numbers_to_hex

type Game = Literal["miloto", "baloto", "revancha"]
type MilotoLotteryNumber = Annotated[int, Field(ge=1, le=settings.miloto.max_value)]
type BalotoRevanchaLotteryNumber = Annotated[int, Field(ge=1, le=settings.baloto.max_value)]
type GameSchema = Annotated[MilotoSchema | BalotoSchema | RevanchaSchema, Field(discriminator="game")]


def _validate_unique_sorted(values: list[int]) -> list[int]:
    """
    Ensure lottery numbers are unique and return them sorted ascending.

    :param values: Raw list of numbers as provided by the caller.
    :returns: The same numbers sorted in ascending order.
    :raises ValueError: If any number appears more than once in ``values``.
    """
    if len(values) != len(set(values)):
        message = "numbers must be unique"
        raise ValueError(message)
    return sorted(values)


type MilotoNumbers = Annotated[
    list[MilotoLotteryNumber],
    Field(min_length=5, max_length=5, title="Numeros Ganadores"),
    AfterValidator(_validate_unique_sorted),
]

type BalotoRevanchaNumbers = Annotated[
    list[BalotoRevanchaLotteryNumber],
    Field(min_length=5, max_length=5, title="Numeros Ganadores"),
    AfterValidator(_validate_unique_sorted),
]


class ResultDetails(BaseModel):
    """
    Prize distribution for a single hit tier of a lottery draw.

    Reused across every hit-count field on the game schemas (e.g. 3, 4,
    or 5 numbers matched, with or without the super balota).
    """

    model_config = ConfigDict(populate_by_name=True, frozen=True)

    prize_for_winner: int = Field(default=0, ge=0, description="Prize per winner", title="Premio por Ganador")
    winners: int = Field(default=0, ge=0, description="Number of winners", title="Ganadores")


class BaseModelSchema(BaseModel, ABC):
    """
    Shared fields and behaviour for a single lottery draw result.

    Concrete game schemas (:class:`MilotoSchema`, :class:`BalotoSchema`,
    :class:`RevanchaSchema`) extend this class to add their own drawn
    numbers, prize tiers, and result URL.
    """

    model_config = ConfigDict(populate_by_name=True, frozen=True)

    game_date: datetime.date
    numbers: list[int]
    hits_3: ResultDetails | None = Field(
        default=None, description="3 hits prize distribution", title="Detalles de 3 aciertos"
    )
    hits_4: ResultDetails | None = Field(
        default=None, description="4 hits prize distribution", title="Detalles de 4 aciertos"
    )
    hits_5: ResultDetails | None = Field(
        default=None, description="5 hits prize distribution", title="Detalles de 5 aciertos"
    )

    # @field_validator("game_date", mode="before")
    @classmethod
    def _convert_es_date(cls, value: object) -> datetime.date:
        """
        Convert an incoming Spanish date string before validation.

        :param value: Raw value as sent by the caller.
        :returns: The parsed date.
        """
        return parse_spanish_date(value)

    @field_validator("game_date", mode="after")
    @classmethod
    def _reject_future_date(cls, value: datetime.date) -> datetime.date:
        """
        Ensure the game date is not in the future.

        :param value: Already-parsed date.
        :returns: The same date.
        :raises ValueError: If ``value`` is later than today.
        """
        if value > datetime.datetime.now(tz=datetime.UTC).date():
            message = "game_date cannot be in the future"
            raise ValueError(message)
        return value

    def _numbers_hex(self, max_value: int) -> str:
        """
        Encode the drawn numbers as a hexadecimal bitmap.

        :param max_value: The highest possible drawn number for this game.
        :returns: The hexadecimal bitmap of the drawn numbers.
        """
        return numbers_to_hex(self.numbers, max_value)

    @computed_field
    @property
    def combination_id(self) -> str:
        """Hexadecimal identifier of the winning number combination."""
        return self.calculate_combination_id()

    @property
    @abstractmethod
    def result_url(self) -> str:
        """URL of the official results page for this game."""
        ...

    @abstractmethod
    def calculate_combination_id(self) -> str:
        """
        Compute the hexadecimal identifier for the winning number combination.

        :returns: The combination id, unique to this draw's winning numbers.
        """


class MilotoSchema(BaseModelSchema):
    """A single Miloto draw result: winning numbers, jackpot, and prize tiers."""

    game: Literal["miloto"] = Field(default="miloto", exclude=True, title="Juego")
    game_id: int = Field(ge=settings.miloto.first_id, title="Sorteo", description="The unique game id")
    game_date: datetime.date = Field(
        ge=settings.miloto.first_date,
        title="Fecha",
        description="The unique game date, must be greater than settings.miloto.first_date",
    )
    numbers: MilotoNumbers
    accumulated: int = Field(
        ge=settings.miloto.min_jackpot,
        title="Acumulado",
        description="The minimum jackpot, must be greater than settings.miloto.min_jackpot",
    )
    hits_2: ResultDetails | None = Field(
        default=None, description="2 hits prize distribution", title="Detalles de 2 aciertos"
    )

    @property
    def result_url(self) -> str:
        """URL of the official Miloto results page."""
        return str(settings.miloto.result_url)

    def calculate_combination_id(self) -> str:
        """
        Compute the hexadecimal identifier for the winning number combination.

        :returns: The combination id encoding the 5 winning numbers.
        """
        return self._numbers_hex(settings.miloto.max_value)


class BalotoSchema(BaseModelSchema):
    """A single Baloto draw result: winning numbers, super balota, jackpot, and prize tiers."""

    game: Literal["baloto"] = Field(default="baloto", exclude=True, title="Juego")
    game_id: int = Field(ge=settings.baloto.first_id, title="Sorteo", description="The unique game id")
    game_date: datetime.date = Field(
        ge=settings.baloto.first_date,
        title="Fecha",
        description="The unique game date, must be greater than settings.baloto.first_date",
    )
    numbers: BalotoRevanchaNumbers
    accumulated: int = Field(
        ge=settings.baloto.min_jackpot,
        title="Acumulado",
        description="The minimum jackpot, must be greater than settings.baloto.min_jackpot",
    )
    super_balota: int = Field(
        ge=1, le=settings.baloto.max_super_balota, description="Super Balota number", title="Super Balota"
    )
    hits_sb: ResultDetails | None = Field(
        default=None, description="Super balota hits prize distribution", title="Detalles acierto de super balota"
    )
    hits_2_sb: ResultDetails | None = Field(
        default=None,
        description="2 hits + super balota prize distribution",
        title="Detalles de 2 aciertos mas Super Balota 2+SB",
    )
    hits_3_sb: ResultDetails | None = Field(
        default=None,
        description="3 hits + super balota prize distribution",
        title="Detalles de 3 aciertos mas Super Balota: 3+SB",
    )
    hits_4_sb: ResultDetails | None = Field(
        default=None,
        description="4 hits + super balota prize distribution",
        title="Detalles de 4 aciertos mas Super Balota: 4+SB",
    )
    hits_5_sb: ResultDetails | None = Field(
        default=None,
        description="5 hits + super balota prize distribution",
        title="Detalles de 5 aciertos mas Super Balota: 5+SB (jackpot)",
    )

    @property
    def result_url(self) -> str:
        """URL of the official Baloto results page."""
        return str(settings.baloto.result_url)

    def calculate_combination_id(self) -> str:
        """
        Compute the hexadecimal identifier for the winning number combination.

        :returns: The combination id encoding the 5 winning numbers and the
            drawn super balota, joined by a colon.
        """
        return f"{self._numbers_hex(settings.baloto.max_value)}:{self.super_balota:X}"


class RevanchaSchema(BalotoSchema):
    """A single Revancha draw result, sharing Baloto's winning numbers and super balota."""

    # Narrowing the discriminator literal is required for the GameSchema union to
    # resolve correctly; pyright's invariance concern doesn't apply since both
    # classes are frozen=True, so `game` can never actually be reassigned.
    game: Literal["revancha"] = Field(  # pyright: ignore[reportIncompatibleVariableOverride]
        default="revancha", exclude=True, title="Juego"
    )
    accumulated: int = Field(
        ge=settings.revancha.min_jackpot,
        title="Acumulado",
        description=f"The minimum jackpot, must be greater than ${settings.revancha.min_jackpot} COP",
    )

    @property
    def result_url(self) -> str:
        """URL of the official Revancha results page."""
        return str(settings.revancha.result_url)


class MilotoDrawListItem(BaseModel):
    """A lightweight Miloto draw row for a frontend data table."""

    model_config = ConfigDict(frozen=True)

    game_id: int
    game_date: str
    numbers: list[int]
    accumulated: str
    jackpot: bool
