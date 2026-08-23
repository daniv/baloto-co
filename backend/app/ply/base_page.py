"""
Provide the shared foundation for asynchronous lottery result page objects.

The module defines the abstract ``BasePage`` navigation lifecycle and the
validator registry owned by each concrete page object. It also contains small
Playwright helpers for reading required text, enforcing exact locator counts,
and converting localized integer values extracted from result documents.
"""

import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from playwright.async_api import Locator, Response, expect

from app.utils.number_utils import es_localized_to_int
from app.utils.playwright_utils.validators import (
    UrlValidator,
    ValidatorRegistry,
)

if TYPE_CHECKING:
    from playwright.async_api import Page
    from pydantic import HttpUrl


_INTEGER_PATTERN = re.compile(r"(\d+(?:\.\d{3})*)")
_WINNING_NUMBERS_COUNT = 5


class BasePage(ABC):
    """
    Provide common navigation, URL construction, and identity validation.

    Concrete lottery page objects supply their game name and base result URL. The
    base class validates the requested draw identifier, builds the final target
    URL, registers URL validation, and runs every page-specific validator after a
    successful Playwright navigation.
    """

    def __init__(
        self,
        page: Page,
        draw_id: int,
    ) -> None:
        """
        Initialize the shared state for a lottery result page.

        The constructor validates the draw identifier, builds the final result URL from
        the concrete page's base URL, and creates a validator registry containing the
        URL validator required by every lottery page.

        :param page: Playwright page used for navigation, validation, and extraction.
        :param draw_id: Positive draw identifier appended to the configured base URL.
        :raises ValueError: If ``draw_id`` is not greater than zero.
        """
        if draw_id <= 0:
            error_message = "draw_id must be greater than zero."
            raise ValueError(error_message)

        self._page = page
        self._draw_id = draw_id
        base_url = str(self._result_url).rstrip("/")
        self._target_url: str = f"{base_url}/{self._draw_id}/"
        self._validators = ValidatorRegistry(
            UrlValidator(self._target_url),
        )

    @abstractmethod
    def _winner_numbers(self) -> Locator:
        """Return the locator containing the five MiLoto winning numbers."""

    @property
    @abstractmethod
    def game_name(self) -> str:
        """Return the canonical name of the lottery game."""

    @property
    @abstractmethod
    def _result_url(self) -> HttpUrl:
        """Return the configured base result URL for the lottery game."""

    @property
    def target_url(self) -> str:
        """Return the complete result URL for the configured draw."""
        return self._target_url

    async def _validate_page_identity(self) -> None:
        """Run every registered validator against the loaded page."""
        await self._validators.validate(self._page)

    @property
    def validators(self) -> ValidatorRegistry:
        """Return the validator registry owned by this page object."""
        return self._validators

    async def open(self) -> Response:
        """
        Navigate to the configured draw and validate the loaded result page.

        The method requires a successful main-document response before executing the
        registered validators in order. Validation exceptions are allowed to propagate
        so callers cannot extract data from a page with an invalid URL or identity.

        :return: Successful main-document HTTP response returned by Playwright.
        :raises RuntimeError: If navigation produces no response.
        :raises RuntimeError: If the server returns an unsuccessful HTTP status.
        :raises AssertionError: If a registered validator rejects the loaded page.
        """
        response = await self._page.goto(self._target_url)

        if response is None:
            error_message = f"Navigation to {self._target_url} produced no response."
            raise RuntimeError(error_message)

        if not response.ok:
            error_message = f"{self.game_name} returned HTTP {response.status} for {response.url}."
            raise RuntimeError(error_message)

        await self._validate_page_identity()
        return response

    async def get_winner_numbers(self) -> list[int]:
        """
        Extract the five Miloto/Baloto/Revancha winning numbers in display order.

        :return: Ordered list containing the five winning numbers.
        :raises AssertionError: If the result does not contain exactly five number nodes.
        :raises ValueError: If any displayed number cannot be converted to an integer.
        """
        winner_numbers = self._winner_numbers()
        await require_exact_count(winner_numbers, _WINNING_NUMBERS_COUNT, "winning numbers")

        number_texts = await winner_numbers.all_inner_texts()

        try:
            return [int(value.strip()) for value in number_texts]
        except ValueError as error:
            error_message = f"Invalid {self.game_name} winning-number values: {number_texts!r}"
            raise ValueError(error_message) from error


async def get_inner_text(
    locator: Locator,
    *,
    timeout_ms: float = 30_000.0,
) -> str:
    """
    Read and normalize the inner text of a locator.

    :param locator: Locator whose inner text will be read.
    :param timeout_ms: Maximum time in milliseconds to wait for the text operation.
    :return: Inner text with leading and trailing whitespace removed.
    :raises TimeoutError: If Playwright cannot read the text before the timeout.
    """
    return (await locator.inner_text(timeout=timeout_ms)).strip()


def extract_detail_integer(value: str, field_name: str, game: str) -> int:
    """
    Extract a localized integer from a result-detail value.

    :param value: Text containing the integer to extract.
    :param field_name: Human-readable field name used in validation errors.
    :param game: Lottery game name used in validation errors.
    :return: Parsed integer after Spanish thousands separators are normalized.
    :raises ValueError: If no supported integer can be found in ``value``.
    """
    match = _INTEGER_PATTERN.search(value)

    if match is None:
        error_message = f"Could not extract the {game} {field_name} value from: {value!r}"
        raise ValueError(error_message)

    return es_localized_to_int(match.group(1))


async def require_exact_count(
    locator: Locator, expected_count: int, field_name: str, *, timeout_ms: float = 5_000.0
) -> None:
    """
    Assert that a locator resolves to an exact number of nodes.

    :param locator: Locator whose matching node count will be validated.
    :param expected_count: Required number of matching nodes.
    :param field_name: Human-readable locator description used in assertion errors.
    :param timeout_ms: Maximum time in milliseconds to wait for the expected count.
    :raises AssertionError: If the locator does not reach ``expected_count`` before the timeout.
    """
    await expect(
        locator,
        f"{field_name} should contain exactly {expected_count} node(s)",
    ).to_have_count(expected_count, timeout=timeout_ms)


async def get_required_text(
    locator: Locator,
    field_name: str,
) -> str:
    """
    Read text from a locator that must resolve to exactly one node.

    :param locator: Locator expected to identify one required element.
    :param field_name: Human-readable field name used in assertion errors.
    :return: Required element text with surrounding whitespace removed.
    :raises AssertionError: If the locator does not resolve to exactly one node.
    :raises TimeoutError: If Playwright cannot read the text before the timeout.
    """
    await require_exact_count(locator, 1, field_name)
    return await get_inner_text(locator)
