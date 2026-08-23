"""
Download and validate lottery result HTML for in-memory extraction.

This module retrieves result-page markup asynchronously with ``httpx`` without
navigating the target website through Playwright. It validates that the server
returned the requested draw rather than silently redirecting to the home page.
"""

import re

import httpx

from app.scraper.exceptions import DrawPageNotFoundError
from app.shared.math_utils import int_to_localized_es

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/142.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
}


async def get_html(url: str, expected_game_id: int, *, timeout_seconds: float = 300.0) -> str:
    """
    Download and validate the HTML document for a specific lottery draw.

    The website may return its home page with a successful HTTP status when a
    requested draw does not exist. The function therefore validates both the
    final response URL and the draw identifier contained in the returned HTML.

    The caller can handle a missing draw independently from network failures:

    Example:
        >>> try:
        ...     html_content = await get_html(url, game_id)
        ... except DrawPageNotFoundError:
        ...     return None

    :param url: Complete draw-result URL requested from the website.
    :param expected_game_id: Draw identifier expected in the returned document.
    :param timeout_seconds: Maximum request duration in seconds.
    :return: Validated response body decoded as text.
    :raises httpx.HTTPError: If the request fails or returns an unsuccessful
        HTTP status.
    :raises DrawPageNotFoundError: If the website redirects to another page or
        returns HTML that does not represent the requested draw.

    """
    async with httpx.AsyncClient(
        headers=HEADERS,
        timeout=timeout_seconds,
        follow_redirects=True,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()

        requested_url = httpx.URL(url)

        if response.url.path.rstrip("/") != requested_url.path.rstrip("/"):
            error_message = (
                f"Draw {expected_game_id} was not found. The website redirected {requested_url} to {response.url}."
            )
            raise DrawPageNotFoundError(error_message)

        formatted_game_id = int_to_localized_es(expected_game_id)
        game_id_pattern = re.compile(
            rf"SORTEO\s+#?{re.escape(formatted_game_id)}\b",
            re.IGNORECASE,
        )

        if game_id_pattern.search(response.text) is None:
            error_message = f"Draw {expected_game_id} was not found in the returned document."
            raise DrawPageNotFoundError(error_message)

        return response.text
