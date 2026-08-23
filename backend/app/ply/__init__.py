"""
Expose the public API for asynchronous lottery result extraction.

The package exports the concrete Playwright page objects for MiLoto, Baloto,
and Revancha together with the structural protocol used by consuming services.
It also exposes the validator registry, validator contract, registration errors,
and the exception raised when a requested draw page cannot be loaded.

Importing from this module provides a stable entry point without requiring
callers to depend on the internal module layout.
"""

from typing import TYPE_CHECKING, Protocol

from app.utils.playwright_utils.baloto_page import BalotoPage, RevanchaPage
from app.utils.playwright_utils.html_loader import DrawPageNotFoundError
from app.utils.playwright_utils.miloto_page import MilotoPage
from app.utils.playwright_utils.validators import (
    DuplicateValidatorError,
    Validator,
    ValidatorNotRegisteredError,
    ValidatorRegistry,
)

if TYPE_CHECKING:
    from playwright.async_api import Response

    from app.schemas.base import ResultDetailsSchema


class ResultPage(Protocol):
    """
    Define the common interface implemented by lottery result page objects.

    The protocol allows services to work with MiLoto, Baloto, and Revancha through
    structural typing. Compatible classes expose a target URL, navigation with
    identity validation, and asynchronous extraction methods for the core result
    fields and payout details.
    """

    @property
    def target_url(self) -> str:
        """Return the complete result URL for the configured draw."""
        ...

    async def get_game_id(self) -> int:
        """
        Extract the identifier displayed for the loaded lottery draw.

        :return: Normalized integer draw identifier.
        :raises ValueError: If the displayed identifier cannot be parsed.
        """
        ...

    async def get_game_date(self) -> str:
        """
        Extract the draw date exactly as displayed by the result page.

        :return: Displayed draw date in Spanish.
        """
        ...

    async def get_winner_numbers(self) -> list[int]:
        """
        Extract the regular winning numbers in display order.

        :return: Ordered winning-number values.
        """
        ...

    async def get_accumulated_prize(self) -> int:
        """
        Extract the accumulated prize normalized to Colombian pesos.

        :return: Accumulated prize as an integer number of pesos.
        :raises ValueError: If the displayed prize cannot be parsed.
        """
        ...

    async def get_details(self) -> dict[str, ResultDetailsSchema]:
        """
        Extract payout details for all supported hit categories with winners.

        :return: Mapping of normalized hit categories to payout details.
        :raises ValueError: If the result structure or categories are invalid.
        """
        ...

    async def get_detail(
        self,
        hits: str,
    ) -> ResultDetailsSchema | None:
        """
        Extract payout details for one requested hit category.

        :param hits: Game-specific hit category to retrieve.
        :return: Payout details, or ``None`` when the category has no winners.
        :raises ValueError: If the category is unsupported or missing from the result.
        """
        ...

    async def open(self) -> Response:
        """
        Navigate to the configured draw and validate the loaded page identity.

        :return: Successful main-document HTTP response.
        :raises RuntimeError: If navigation produces no response or an unsuccessful HTTP status.
        :raises AssertionError: If a registered validator rejects the loaded page.
        """
        ...


__all__ = [
    "BalotoPage",
    "DrawPageNotFoundError",
    "DuplicateValidatorError",
    "MilotoPage",
    "ResultPage",
    "RevanchaPage",
    "Validator",
    "ValidatorNotRegisteredError",
    "ValidatorRegistry",
]
