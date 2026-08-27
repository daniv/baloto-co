"""
CLI to scrape-and-save one draw each for Miloto, Baloto, and Revancha.

Calls the running API's admin-gated ``POST /{game}/draw/{draw_id}`` route
for each game in turn (see :mod:`app.games.router`); the app itself drives
Playwright and builds/validates the payload, this script only triggers it.
"""

import argparse
import sys
from dataclasses import dataclass

import httpx
from app.core.config import settings
from app.shared.console import console, error_console


@dataclass(frozen=True)
class GameDraw:
    """One game/draw_id pair to load, in the order it should be requested."""

    game: str
    draw_id: int


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse CLI arguments for the three draw ids and the target server."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("miloto_id", type=int, help="Miloto draw_id to scrape and save")
    parser.add_argument("baloto_id", type=int, help="Baloto draw_id to scrape and save")
    parser.add_argument("revancha_id", type=int, help="Revancha draw_id to scrape and save")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Base URL of the running API (default: %(default)s)",
    )
    return parser.parse_args(argv)


def _load_draw(client: httpx.Client, draw: GameDraw) -> bool:
    """
    POST one game's draw to the running API and print the outcome.

    :param client: Shared HTTP client, already carrying the admin auth header.
    :param draw: Which game and draw_id to request.
    :return: True if the API returned a successful (2xx) response.
    """
    response = client.post(f"/{draw.game}/draw/{draw.draw_id}")

    if response.is_success:
        console.print(f"[bold green][{draw.game}][/] draw {draw.draw_id}: OK\n{response.json()}")
        return True

    error_console.print(
        f"[bold red][{draw.game}][/] draw {draw.draw_id}: FAILED ({response.status_code})\n{response.text}"
    )
    return False


def main(argv: list[str] | None = None) -> int:
    """
    Load one draw each for Miloto, Baloto, and Revancha, in that order.

    :param argv: Command-line arguments, or ``None`` to use ``sys.argv``.
    :return: Process exit code: 0 if every draw loaded successfully, 1 otherwise.
    """
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    draws = [
        GameDraw("miloto", args.miloto_id),
        GameDraw("baloto", args.baloto_id),
        GameDraw("revancha", args.revancha_id),
    ]

    headers = {"X-Admin-Api-Key": settings.admin_api_key.get_secret_value()}
    try:
        with httpx.Client(base_url=args.base_url, headers=headers, timeout=60.0) as client:
            results = [_load_draw(client, draw) for draw in draws]
    except httpx.ConnectError as error:
        error_console.print(f"[bold red]Could not reach {args.base_url}[/] — is the API running (`uv run poe serve`)?")
        error_console.print(str(error))
        return 1

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
