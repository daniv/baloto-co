"""Shared Playwright browser/context lifecycle for the running application."""

from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, Self

# Request must stay a real (not TYPE_CHECKING-only) import: FastAPI resolves
# get_page's parameter annotations at runtime to recognize its special
# injectable types -- same constraint as app.games.models/app.games.router.
from playwright.async_api import async_playwright

from app.core.config import settings

if TYPE_CHECKING:
    from types import TracebackType

    from playwright.async_api import BrowserContext, Page


class PlaywrightClient:
    """
    Own the Chromium browser and context shared by the whole running application.

    Used as an async context manager, typically for the lifetime of the
    FastAPI app via its ``lifespan`` handler::

        async with PlaywrightClient() as client:
            app.state.playwright_client = client
            yield

    Unlike the test-suite browser context, this one keeps JavaScript enabled
    and does not set ``offline=True``: it performs real navigation against
    the live result pages, not extraction from injected HTML.
    """

    def __init__(self) -> None:
        """Initialize an unstarted client; enter it with ``async with`` before use."""
        self._exit_stack = AsyncExitStack()
        self._context: BrowserContext | None = None

    async def __aenter__(self) -> Self:
        """Launch Chromium and open the shared browser context."""
        playwright = await self._exit_stack.enter_async_context(async_playwright())
        browser = await playwright.chromium.launch(headless=settings.playwright_headless)
        self._exit_stack.push_async_callback(browser.close)
        self._context = await browser.new_context(locale="es-CO")
        self._exit_stack.push_async_callback(self._context.close)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the context, browser, and Playwright driver, in that order."""
        await self._exit_stack.__aexit__(exc_type, exc_value, traceback)
        self._context = None

    async def new_page(self) -> Page:
        """
        Create a fresh, isolated page from the shared browser context.

        :return: A new page; the caller is responsible for closing it.
        :raises RuntimeError: If called outside this client's ``async with`` block.
        """
        if self._context is None:
            error_message = "PlaywrightClient.new_page() was called outside its 'async with' block."
            raise RuntimeError(error_message)

        return await self._context.new_page()
