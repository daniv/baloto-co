"""
CLI to scrape-and-save one draw for any of Miloto, Baloto, and Revancha.

Calls the running API's admin-gated ``POST /{game}/draw/{draw_id}`` route
for each game passed (see :mod:`app.games.router`); the app itself drives
Playwright and builds/validates the payload, this script only triggers it.
Pass only the games you want loaded -- e.g. just ``--miloto`` to load a
single Miloto draw.
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
    """Parse CLI arguments for the requested draw ids and the target server."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--miloto", type=int, default=None, metavar="DRAW_ID", help="Miloto draw_id to scrape and save")
    parser.add_argument("--baloto", type=int, default=None, metavar="DRAW_ID", help="Baloto draw_id to scrape and save")
    parser.add_argument(
        "--revancha", type=int, default=None, metavar="DRAW_ID", help="Revancha draw_id to scrape and save"
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Base URL of the running API (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    if args.miloto is None and args.baloto is None and args.revancha is None:
        parser.error("provide at least one of --miloto, --baloto, --revancha")

    return args


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
    Load one draw for each requested game, in Miloto/Baloto/Revancha order.

    :param argv: Command-line arguments, or ``None`` to use ``sys.argv``.
    :return: Process exit code: 0 if every requested draw loaded successfully, 1 otherwise.
    """
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    requested = [("miloto", args.miloto), ("baloto", args.baloto), ("revancha", args.revancha)]
    draws = [GameDraw(game, draw_id) for game, draw_id in requested if draw_id is not None]

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
