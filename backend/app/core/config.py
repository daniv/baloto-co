from datetime import date
import calendar
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
    PyprojectTomlConfigSettingsSource,
    PydanticBaseSettingsSource,
)
from pydantic import Field, HttpUrl, SecretStr, PostgresDsn, computed_field, model_validator
from typing import Self


class GameSettings(BaseSettings):
    model_config = SettingsConfigDict(frozen=True, extra="forbid")

    numbers_count: int = Field(default=5, description="The total numbers for miloto")


class MilotoSettings(GameSettings):
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
    min_hits_prize: int = Field(default=3_000, description="The lowest revancha prize for SB acert, in COP")
    result_url: HttpUrl = Field(
        default_factory=lambda: HttpUrl("https://www.baloto.com/resultados-revancha/"),
        description="the revancha base results URL",
    )


class BackendSettings(BaseSettings):
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

    # frozen=True per-field: instance can't be swapped out even though # BackendSettings itself isn't fully frozen
    miloto: MilotoSettings = Field(default_factory=MilotoSettings, frozen=True)
    baloto: BalotoSettings = Field(default_factory=BalotoSettings, frozen=True)
    revancha: RevanchaSettings = Field(default_factory=RevanchaSettings, frozen=True)

    verbosity: int = Field(default=0, title="Dev mode verbosity", frozen=False)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
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
    def verify_db_password_is_changed(self) -> Self:
        """
        Reject the insecure default database password during validation.

        :return: The validated database settings instance.
        :raises ValueError: If the configured database password is still ``CHANGE_ME``.
        """
        if self.db_password.get_secret_value() == "CHANGE_ME":
            err_msg = "Security Alert: You must override the default DB password!"
            raise ValueError(err_msg)
        return self


settings = BackendSettings()
