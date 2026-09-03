"""
CLI to scrape one live draw for any of Miloto, Baloto, and Revancha, and save it.

Drives Playwright itself to scrape and validate each requested draw (see
:func:`app.games.scrape_service.scrape_draw`). By default, the validated
payload is then POSTed to the running API's DB-only
``POST /{game}/draw/{draw_id}`` route (see :mod:`app.games.router`) to
persist it, so the API must already be running (``uv run poe serve``) and
reachable at ``--base-url``. Pass ``--json`` to skip the API entirely and
write each payload to ``scripts/resources/<game>_<draw_id>.json`` instead,
which needs neither a running API nor database access.

Pass only the games you want loaded -- e.g. just ``--miloto`` to load a
single Miloto draw. Multiple games may be combined in one invocation; each
requested game/draw_id pair is scraped and persisted independently, so one
game failing does not stop the others from being attempted.

Exit code is ``0`` only if every requested draw was scraped and persisted
successfully; ``1`` otherwise (a scrape failure, a non-2xx API response, or
the API being unreachable when not using ``--json``).
"""

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from app.core.config import settings
from app.games.scrape_service import scrape_draw
from app.scraper.playwright_client import PlaywrightClient
from app.shared.console import console, error_console

if TYPE_CHECKING:
    from app.games.schemas import Game, GameSchema

RESOURCES_DIR = Path(__file__).parent / "resources"


@dataclass(frozen=True)
class GameDraw:
    """
    One game/draw_id pair to load, in the order it should be requested.

    :ivar game: Which game the draw belongs to.
    :ivar draw_id: The draw's identifier, as scraped from and validated against the live results page.
    """

    game: Game
    draw_id: int


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """
    Parse CLI arguments for the requested draw ids, the target server, and the ``--json`` output mode.

    :param argv: Command-line arguments to parse, excluding the program name (i.e. already sliced
        the way ``sys.argv[1:]`` would be).
    :returns: The parsed namespace, exposing ``miloto``, ``baloto``, ``revancha`` (each an
        ``int | None`` draw id), ``base_url`` (``str``), and ``json`` (``bool``).
    :raises SystemExit: If none of ``--miloto``/``--baloto``/``--revancha`` was passed, or if
        ``argparse`` itself rejects the arguments (e.g. a non-integer draw id).
    """
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
    parser.add_argument(
        "--json",
        action="store_true",
        help=("Skip the API and instead save each scraped draw to scripts/resources/<game>_<draw_id>.json."),
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args(argv)

    if args.miloto is None and args.baloto is None and args.revancha is None:
        parser.error("provide at least one of --miloto, --baloto, --revancha")

    return args


def _create_payload(result: GameSchema, *, verbose: bool = False) -> dict[str, object]:
    """
    Build the DB-create request body from a scraped, validated schema.

    ``combination_id`` is excluded because it is a computed field the schema derives from the
    winning numbers (see :mod:`app.games.schemas`) -- the API recomputes it server-side rather
    than trusting a client-supplied value, and would reject it as an unknown field otherwise.

    :param result: The validated draw returned by :func:`app.games.scrape_service.scrape_draw`.
    :param verbose: make the function log
    :returns: A JSON-safe ``dict`` suitable both as an HTTP request body and for writing to disk.
    """
    if verbose:
        console.log("dumping result model")

    return result.model_dump(mode="json", exclude={"combination_id"})


def _save_json(game: Game, draw_id: int, payload: dict[str, object], *, verbose: bool = False) -> Path:
    """
    Write a scraped draw's payload to ``scripts/resources/<game>_<draw_id>.json``.

    Creates :data:`RESOURCES_DIR` if it does not already exist. An existing file for the same
    game/draw_id is silently overwritten.

    :param game: Which game the draw belongs to; used as the filename prefix.
    :param draw_id: The draw's identifier; used as the filename suffix.
    :param payload: The JSON-safe payload to write, as produced by :func:`_create_payload`.
    :returns: The path the payload was written to.
    :raises OSError: If the resources directory can't be created or the file can't be written
        (e.g. a permissions error, or a path component already existing as a non-directory file).
    """
    RESOURCES_DIR.mkdir(parents=True, exist_ok=True)
    file_path = RESOURCES_DIR / f"{game}_{draw_id}.json"
    if verbose:
        console.log(f"creating {file_path} file")
        console.log(f"writing payload: {payload}")
    file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return file_path


async def _load_draw(
    playwright_client: PlaywrightClient, http_client: httpx.AsyncClient | None, draw: GameDraw, *, verbose: bool = False
) -> bool:
    """
    Scrape one game's draw and either POST it to the API or save it as JSON, printing the outcome.

    :param playwright_client: Shared browser client used to scrape the live page.
    :param http_client: Shared HTTP client, already carrying the admin auth header, or
        ``None`` to save the scraped draw as JSON instead of calling the API.
    :param draw: Which game and draw_id to request.
    :return: True if scraping and persisting both succeeded.
    """
    if verbose:
        console.log("Creating a new playwright page object")
    page = await playwright_client.new_page()
    try:
        if verbose:
            console.log(f"Parsing the {draw.game} html document, id={draw.draw_id}")
        result = await scrape_draw(page, draw.game, draw.draw_id)
    except Exception as error:  # noqa: BLE001 - scrape failures are surfaced and skipped, not propagated.
        error_console.print(f"[bold red][{draw.game}][/] draw {draw.draw_id}: SCRAPE FAILED\n{error}")
        return False
    finally:
        await page.close()

    payload = _create_payload(result)

    if http_client is None:
        file_path = _save_json(draw.game, draw.draw_id, payload)
        console.print(f"[bold green][{draw.game}][/] draw {draw.draw_id}: SAVED to {file_path}")
        return True

    response = await http_client.post(f"/{draw.game}/draw/{draw.draw_id}", json=payload)

    if response.is_success:
        console.print(f"[bold green][{draw.game}][/] draw {draw.draw_id}: OK\n{response.json()}")
        return True

    error_console.print(
        f"[bold red][{draw.game}][/] draw {draw.draw_id}: FAILED ({response.status_code})\n{response.text}"
    )
    return False


async def _load_draws(draws: list[GameDraw], base_url: str, *, as_json: bool, verbose: bool = False) -> list[bool]:
    """Scrape and persist every requested draw, sharing one browser and (unless saving JSON) one HTTP client."""
    if as_json:
        console.log("The script will store the draws on a json file")
        async with PlaywrightClient() as playwright_client:
            return [await _load_draw(playwright_client, None, draw, verbose=verbose) for draw in draws]

    console.log("The script will store the draws the database using API POST request")
    headers = {"X-Admin-Api-Key": settings.admin_api_key.get_secret_value()}
    async with (
        PlaywrightClient() as playwright_client,
        httpx.AsyncClient(base_url=base_url, headers=headers, timeout=60.0) as http_client,
    ):
        return [await _load_draw(playwright_client, http_client, draw, verbose=verbose) for draw in draws]


def main(argv: list[str] | None = None) -> int:
    """
    Load one draw for each requested game, in Miloto/Baloto/Revancha order.

    :param argv: Command-line arguments, or ``None`` to use ``sys.argv``.
    :return: Process exit code: 0 if every requested draw loaded successfully, 1 otherwise.
    """
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    requested: list[tuple[Game, int | None]] = [
        ("miloto", args.miloto),
        ("baloto", args.baloto),
        ("revancha", args.revancha),
    ]
    draws = [GameDraw(game, draw_id) for game, draw_id in requested if draw_id is not None]

    try:
        results = asyncio.run(_load_draws(draws, args.base_url, as_json=args.json, verbose=args.verbose))
    except httpx.ConnectError as error:
        error_console.print(f"[bold red]Could not reach {args.base_url}[/] — is the API running (`uv run poe serve`)?")
        error_console.print(str(error))
        return 1

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
