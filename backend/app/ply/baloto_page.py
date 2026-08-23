"""
Provide concrete asynchronous page objects for Baloto and Revancha results.

Both page objects inherit the shared Baloto-style extraction behavior and add
the game-specific base URL and identity validators required during navigation.
Baloto and Revancha therefore expose the same extraction API while preserving
independent page-identity checks for their production pages and test fixtures.
"""

from typing import TYPE_CHECKING

from app.config.app_settings import settings
from app.utils.playwright_utils.shared import BalotoRevanchaSharedResultPage
from app.utils.playwright_utils.validators import BalotoImageValidator, DrawIdValidator, RevanchaImageValidator

if TYPE_CHECKING:
    from playwright.async_api import Page
    from pydantic import HttpUrl


class BalotoPage(BalotoRevanchaSharedResultPage):
    """
    Represent and validate an individual Baloto draw result page.

    The page object reuses the shared Baloto/Revancha extraction implementation,
    configures the Baloto result URL, and registers validators for the Baloto page
    identity and expected draw identifier.
    """

    def __init__(self, page: Page, draw_id: int) -> None:
        """
        Initialize a Baloto page object for a specific draw.

        The constructor initializes the shared result-page state and registers the
        Baloto identity marker and draw-identifier validators.

        :param page: Playwright page used to navigate and extract the Baloto result.
        :param draw_id: Positive Baloto draw identifier expected in the loaded page.
        :raises ValueError: If ``draw_id`` is not greater than zero.
        :raises DuplicateValidatorError: If a validator name is already registered.
        """
        super().__init__(page, draw_id)
        self.validators.register(BalotoImageValidator(), DrawIdValidator(draw_id, self._game_id))

    @property
    def _result_url(self) -> HttpUrl:
        """Return the configured Baloto results URL."""
        return settings.baloto_settings.baloto_baseurl

    @property
    def game_name(self) -> str:
        """Return the canonical Baloto game name."""
        return "Baloto"


class RevanchaPage(BalotoRevanchaSharedResultPage):
    """
    Represent and validate an individual Revancha draw result page.

    The page object reuses the shared Baloto/Revancha extraction implementation,
    configures the Revancha result URL, and registers validators for the Revancha
    page identity and expected draw identifier.
    """

    def __init__(self, page: Page, draw_id: int) -> None:
        """
        Initialize a Revancha page object for a specific draw.

        The constructor initializes the shared result-page state and registers the
        Revancha identity marker and draw-identifier validators.

        :param page: Playwright page used to navigate and extract the Revancha result.
        :param draw_id: Positive Revancha draw identifier expected in the loaded page.
        :raises ValueError: If ``draw_id`` is not greater than zero.
        :raises DuplicateValidatorError: If a validator name is already registered.
        """
        super().__init__(page, draw_id)
        self.validators.register(RevanchaImageValidator(), DrawIdValidator(draw_id, self._game_id))

    @property
    def _result_url(self) -> HttpUrl:
        """Return the configured Revancha results URL."""
        return settings.baloto_settings.revancha_baseurl

    @property
    def game_name(self) -> str:
        """Return the canonical Revancha game name."""
        return "Revancha"
