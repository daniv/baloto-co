"""
Provide composable asynchronous validators for lottery result pages.

The module defines the structural validator contract, an ordered registry with
atomic duplicate detection, and concrete validators for URLs, displayed draw
identifiers, MiLoto metadata and titles, and Baloto/Revancha identity markers.
Validators use Playwright assertions so page objects fail before extraction
when a loaded document does not represent the requested game or draw.
"""

import re
from collections import Counter
from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol

from babel.dates import format_date
from playwright.async_api import Locator, Page, expect

from app.scraper.exceptions import DuplicateValidatorError, ValidatorNotRegisteredError
from app.shared.math_utils import int_to_localized_es

if TYPE_CHECKING:
    from datetime import date

type LocatorFactory = Callable[[Page], Locator]


class Validator(Protocol):
    """
    Define the structural contract for asynchronous page validators.

    Each validator exposes a stable registration name and validates one aspect of
    a loaded Playwright page. Implementations may retain expected values such as a
    URL or draw identifier while remaining independent of the page-object class.
    """

    @property
    def name(self) -> str:
        """Return the stable name used by the validator registry."""
        ...

    async def validate(self, page: Page) -> None:
        """
        Validate one aspect of a loaded Playwright page.

        :param page: Loaded Playwright page to validate.
        :raises AssertionError: If the page does not satisfy the validator contract.
        """
        ...


class ValidatorRegistry:
    """
    Manage validators as an ordered, uniquely named collection.

    Registration preserves execution order and is atomic when duplicates are
    found. Validators can be queried, removed individually, removed as a group, or
    executed sequentially against a loaded Playwright page.
    """

    def __init__(self, *validators: Validator) -> None:
        """
        Initialize the registry with an optional validator sequence.

        Initial validators are registered atomically in the supplied execution order.

        :param validators: Validators to register during construction.
        :raises DuplicateValidatorError: If any supplied validator name is duplicated.
        """
        self._validators: list[Validator] = []
        self.register(*validators)

    @property
    def validators(self) -> tuple[Validator, ...]:
        """Return registered validators in execution order."""
        return tuple(self._validators)

    def has(self, name: str) -> bool:
        """
        Check whether a validator name is registered.

        :param name: Validator name to search for.
        :return: ``True`` when the name is registered; otherwise ``False``.
        """
        return any(validator.name == name for validator in self._validators)

    def register(self, *validators: Validator) -> None:
        """
        Register validators in the supplied execution order.

        The operation is atomic: no validator is added when a supplied name already
        exists or appears more than once in the same registration call.

        :param validators: Validators to register.
        :raises DuplicateValidatorError: If one or more validator names are duplicated.
        """
        registered_names = {validator.name for validator in self._validators}
        supplied_name_counts = Counter(validator.name for validator in validators)

        duplicated_names = {
            name for name, count in supplied_name_counts.items() if count > 1 or name in registered_names
        }

        if duplicated_names:
            raise DuplicateValidatorError(tuple(sorted(duplicated_names)))

        self._validators.extend(validators)

    def unregister(self, name: str) -> Validator:
        """
        Remove and return one validator by name.

        :param name: Name of the validator to remove.
        :return: Removed validator instance.
        :raises ValidatorNotRegisteredError: If the requested name is not registered.
        """
        for index, validator in enumerate(self._validators):
            if validator.name == name:
                return self._validators.pop(index)

        raise ValidatorNotRegisteredError(name)

    def unregister_all(self) -> tuple[Validator, ...]:
        """
        Remove every registered validator while preserving former order.

        :return: Removed validators in their previous execution order.
        """
        removed_validators = tuple(self._validators)
        self._validators.clear()
        return removed_validators

    async def validate(self, page: Page) -> None:
        """
        Execute every registered validator in registration order.

        Validation stops immediately when a validator raises an exception.

        :param page: Loaded Playwright page to validate.
        :raises AssertionError: If any registered validator rejects the page.
        """
        for validator in self._validators:
            await validator.validate(page)


class UrlValidator:
    """
    Validate the final URL of a loaded result page.

    The expected target URL is stored during construction and compared through a
    Playwright URL assertion when validation runs.
    """

    def __init__(self, url: str) -> None:
        """
        Initialize URL validation for one expected target.

        :param url: Complete result URL expected after navigation.
        """
        self._target_url = url

    @property
    def name(self) -> str:
        """Return the stable URL-validator name."""
        return "url"

    async def validate(self, page: Page) -> None:
        """
        Verify that the loaded page URL matches the expected target.

        :param page: Loaded Playwright page to validate.
        :raises AssertionError: If the current URL does not match the expected URL.
        """
        await expect(
            page,
            f"Loaded page URL should match {self._target_url!r}",
        ).to_have_url(self._target_url)


class DrawIdValidator:
    """
    Validate the draw identifier displayed by a result page.

    The validator formats the expected integer using Spanish thousands separators
    and delegates locator creation to the supplied page-aware factory. The factory
    may further restrict accepted formatting for a specific lottery page.
    """

    def __init__(
        self,
        draw_id: int,
        locator_factory: LocatorFactory,
    ) -> None:
        """
        Initialize validation for one expected draw identifier.

        :param draw_id: Draw identifier expected in the loaded result document.
        :param locator_factory: Callable that receives a Playwright page and returns the draw-identifier locator.
        """
        self._draw_id = draw_id
        self._locator_factory = locator_factory

    @property
    def name(self) -> str:
        """Return the stable draw-identifier validator name."""
        return "draw_id"

    async def validate(self, page: Page) -> None:
        """
        Verify that the page displays the expected draw identifier.

        The comparison accepts the localized identifier with the validator's supported
        ``SORTEO`` prefix format. The locator factory can impose stricter game-specific
        matching before the assertion is evaluated.

        :param page: Loaded Playwright page passed to the locator factory.
        :raises AssertionError: If the displayed identifier does not match the expected draw.
        """
        localized_draw_id = int_to_localized_es(self._draw_id)
        expected_text = re.compile(
            rf"^\s*SORTEO\s+#?{re.escape(localized_draw_id)}\s*$",
            re.IGNORECASE,
        )

        await expect(
            self._locator_factory(page),
            f"Loaded page should display draw {self._draw_id}",
        ).to_have_text(expected_text)


class MetaContentValidator:
    """
    Validate the Miloto identity declared by page metadata.

    This validator targets the description meta element used by Miloto result
    pages and verifies its exact game-identifying content.
    """

    @property
    def name(self) -> str:
        """Return the stable metadata-validator name."""
        return "meta content"

    async def validate(self, page: Page) -> None:
        """
        Verify that the page metadata identifies Miloto.

        :param page: Loaded Playwright page to validate.
        :raises AssertionError: If the description metadata does not contain ``Miloto``.
        """
        description = page.locator(
            'meta[name="description"]',
        ).describe("Miloto meta description tag")

        await expect(
            description,
            "Loaded page metadata should identify the Miloto game",
        ).to_have_attribute("content", "Miloto")


class PageTitleValidator:
    """
    Validate the Miloto identity declared by the document title.

    The validator is intentionally specific to Miloto pages, whose title provides
    a reliable identity marker for result extraction.
    """

    @property
    def name(self) -> str:
        """Return the stable page-title validator name."""
        return "page title"

    async def validate(self, page: Page) -> None:
        """
        Verify that the loaded page title identifies Miloto.

        :param page: Loaded Playwright page to validate.
        :raises AssertionError: If the page title is not exactly ``Miloto``.
        """
        await expect(page, "Loaded page title should identify the Miloto game").to_have_title("MiLoto", timeout=500)


class RevanchaImageValidator:
    """
    Validate the presence of a Revancha page-identity marker.

    The combined locator supports the deterministic body marker used by tests and
    the Revancha image marker available on the production result page.
    """

    @property
    def name(self) -> str:
        """Return the stable Revancha-image validator name."""
        return "revancha image"

    async def validate(self, page: Page) -> None:
        """
        Verify that at least one Revancha identity marker is attached.

        :param page: Loaded Playwright page to validate.
        :raises AssertionError: If neither supported Revancha marker is attached.
        """
        result_image = page.locator(
            'body[data-game="revancha"], img[src$="revancha.png"]',
        ).describe("Revancha result image")

        await expect(
            result_image.first,
            "The loaded page should contain at least one Revancha identity marker",
        ).to_be_attached(timeout=5_000.0)


class BalotoImageValidator:
    """
    Validate the presence of a Baloto page-identity marker.

    The combined locator supports the deterministic body marker used by tests and
    the Baloto image marker available on the production result page.
    """

    @property
    def name(self) -> str:
        """Return the stable Baloto-image validator name."""
        return "baloto image"

    async def validate(self, page: Page) -> None:
        """
        Verify that at least one Baloto identity marker is attached.

        :param page: Loaded Playwright page to validate.
        :raises AssertionError: If neither supported Baloto marker is attached.
        """
        result_image = page.locator(
            'body[data-game="baloto"], img[src$="baloto.png"]',
        ).describe("Baloto result image")

        await expect(
            result_image.first,
            "The loaded page should contain at least one Baloto identity marker",
        ).to_be_attached(timeout=5_000.0)


class DateValidator:
    """Validate the draw date displayed by a lottery result page."""

    def __init__(self, expected_date: date, locator_factory: LocatorFactory) -> None:
        """
        Initialize the draw-date validator.

        The expected date is stored as a domain value rather than as localized
        text. The locator factory allows the same validator to work with the
        different HTML structures used by Miloto, Baloto, and Revancha.

        :param expected_date: Calendar date expected in the loaded result page.
        :param locator_factory: Callable that returns the draw-date locator.
        """
        self._expected_date = expected_date
        self._locator_factory = locator_factory

    @property
    def name(self) -> str:
        """Return the validator name."""
        return "game_date"

    async def validate(self, page: Page) -> None:
        """
        Verify that the page displays the expected draw date.

        The expected value is formatted in Spanish and compared
        case-insensitively. Flexible whitespace is accepted so minor
        presentation differences do not change the represented date.

        :param page: Loaded Playwright page to validate.
        :raises AssertionError: If the displayed draw date does not match the expected date.
        """
        localized_date = format_date(
            self._expected_date,
            "d 'de' MMMM 'de' y",
            locale="es_CO",
        )
        date_parts = (re.escape(part) for part in localized_date.split())
        expected_text = re.compile(rf"^\s*{r'\s+'.join(date_parts)}\s*$", re.IGNORECASE)

        await expect(
            self._locator_factory(page),
            f"Loaded page should display draw date {localized_date!r}",
        ).to_have_text(expected_text)
