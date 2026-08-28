"""Application settings, including per-game lottery configuration."""

import calendar
from datetime import date
from typing import Self

from pydantic import Field, HttpUrl, PostgresDsn, SecretStr, computed_field, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    PyprojectTomlConfigSettingsSource,
    SettingsConfigDict,
)


class GameSettings(BaseSettings):
    """
    Base settings shared by every lottery game.

    Subclassed by each game's settings (:class:`MilotoSettings`,
    :class:`BalotoSettings`) to add the game-specific numeric bounds,
    historical draw data, and result URL.
    """

    model_config = SettingsConfigDict(frozen=True, extra="forbid")

    winning_numbers_count: int = Field(default=5, description="The total numbers for miloto")


class MilotoSettings(GameSettings):
    """
    Fixed configuration for the Miloto lottery game.

    Holds the historical first draw id/date, the numeric bounds for the
    5 drawn numbers, the jackpot and hit-prize floors, the weekdays
    Miloto is drawn, and the base results URL.
    """

    first_id: int = Field(default=1, description="First miloto draw number")
    first_date: date = Field(default=date(2023, 10, 23), description="The fist miloto draw date")
    min_jackpot: int = Field(default=120_000_000, description="The minimum miloto jackpot prize in COP")
    min_hits_prize: int = Field(default=4_000, description="The lowest prize for 2 acerts, in COP")
    max_value: int = Field(default=39, description="The max miloto number option to select")
    draw_weekdays: list[int] = Field(
        default=[calendar.MONDAY, calendar.TUESDAY, calendar.THURSDAY, calendar.FRIDAY],
        description="The weekdys that miloto plays",
    )
    result_url: HttpUrl = Field(
        default_factory=lambda: HttpUrl("https://www.baloto.com/miloto/resultados-miloto/"),
        description="the miloto base results URL",
    )


class BalotoSettings(GameSettings):
    """
    Fixed configuration for the Baloto lottery game.

    Holds the historical first draw id/date, the numeric bounds for the
    5 drawn numbers and the super balota, the jackpot and hit-prize
    floors, the weekdays Baloto is drawn, and the base results URL.
    """

    model_config = SettingsConfigDict(frozen=True, extra="forbid")

    first_id: int = Field(default=2082, description="First baloto/revancha draw number")
    first_date: date = Field(default=date(2021, 5, 5), description="The fist baloto/revancha draw date")
    min_jackpot: int = Field(default=2_000_000_000, description="The minimum baloto/revancha jackpot prize in COP")
    min_hits_prize: int = Field(default=6_000, description="The lowest baloto prize for SB acert, in COP")
    max_value: int = Field(default=43, description="The max baloto/revancha number option to select")
    max_super_balota: int = Field(default=16, description="The max super-balota value for baloto/revancha")
    draw_weekdays: list[int] = Field(
        default=[calendar.MONDAY, calendar.WEDNESDAY, calendar.SATURDAY],
        description="The weekdys that baloto/revancha plays",
    )
    result_url: HttpUrl = Field(
        default_factory=lambda: HttpUrl("https://www.baloto.com/resultados-baloto/"),
        description="the baloto base results URL",
    )


class RevanchaSettings(BalotoSettings):
    """
    Fixed configuration for the Revancha lottery game.

    Revancha is drawn from the same balls as Baloto, so it inherits all
    of :class:`BalotoSettings` and only overrides the hit-prize floor
    and the base results URL.
    """

    min_hits_prize: int = Field(default=3_000, description="The lowest revancha prize for SB acert, in COP")
    result_url: HttpUrl = Field(
        default_factory=lambda: HttpUrl("https://www.baloto.com/resultados-revancha/"),
        description="the revancha base results URL",
    )


class BackendSettings(BaseSettings):
    """
    Top-level application settings, loaded from the environment and ``pyproject.toml``.

    Aggregates the database connection settings and the per-game
    settings (:attr:`miloto`, :attr:`baloto`, :attr:`revancha`) into a
    single settings object exposed as the module-level ``settings``
    singleton.
    """

    model_config = SettingsConfigDict(
        validate_default=True,
        case_sensitive=False,
        env_file="../.env",
        env_file_encoding="utf-8",
        pyproject_toml_table_header=("project",),
        extra="ignore",
    )

    name: str = ""
    version: str = "0.0.0"
    description: str = ""

    db_user: str = "postgres"
    db_password: SecretStr = Field(default_factory=lambda: SecretStr("CHANGE_ME"))
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "baloto_co"
    db_name_test: str = "test"

    admin_api_key: SecretStr = Field(
        default_factory=lambda: SecretStr("CHANGE_ME"),
        description="Shared secret required on the X-Admin-Api-Key header to call admin-only write endpoints.",
    )

    # frozen=True per-field: instance can't be swapped out even though # BackendSettings itself isn't fully frozen
    miloto: MilotoSettings = Field(default_factory=MilotoSettings, frozen=True)
    baloto: BalotoSettings = Field(default_factory=BalotoSettings, frozen=True)
    revancha: RevanchaSettings = Field(default_factory=RevanchaSettings, frozen=True)

    verbosity: int = Field(default=0, title="Dev mode verbosity", frozen=False)

    playwright_headless: bool = Field(
        default=True,
        description="Whether the shared Chromium browser launches headless. Set to False to watch it navigate.",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """
        Order the settings sources consulted when building this model.

        :param settings_cls: The settings class being instantiated.
        :param init_settings: Values passed directly to the constructor.
        :param env_settings: Values read from environment variables.
        :param dotenv_settings: Values read from the ``.env`` file.
        :param file_secret_settings: Values read from secret files.
        :returns: The sources in priority order, highest priority first.
        """
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            PyprojectTomlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )

    @computed_field
    @property
    def pg_dsn(self) -> PostgresDsn:
        """
        The async database connection string used by the SQLAlchemy engine.

        :return: A validated Postgres DSN using the asyncpg driver.
        """
        secret_value = self.db_password.get_secret_value()
        return PostgresDsn(
            f"postgresql+asyncpg://{self.db_user}:{secret_value}@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @model_validator(mode="after")
    def verify_secrets_are_changed(self) -> Self:
        """
        Reject insecure default values for every secret setting.

        :return: The validated settings instance.
        :raises ValueError: If ``db_password`` or ``admin_api_key`` is still ``CHANGE_ME``.
        """
        _reject_default_secret(self.db_password, "db_password")
        _reject_default_secret(self.admin_api_key, "admin_api_key")
        return self


def _reject_default_secret(value: SecretStr, field_name: str) -> None:
    """Raise if a secret setting still holds its insecure ``CHANGE_ME`` placeholder."""
    if value.get_secret_value() == "CHANGE_ME":
        error_message = f"Security Alert: You must override the default {field_name}!"
        raise ValueError(error_message)


settings = BackendSettings()
