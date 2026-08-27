"""Scrape one live draw result page into its validated pydantic schema."""

from typing import TYPE_CHECKING

from app.games.schemas import BalotoSchema, Game, GameSchema, MilotoSchema, RevanchaSchema
from app.scraper import BalotoResultPage, DrawPageNotFoundError, MilotoResultPage, RevanchaResultPage
from app.shared.date_utils import parse_spanish_date

if TYPE_CHECKING:
    from playwright.async_api import Page


def _build_result_page(
    game: Game, page: Page, draw_id: int
) -> MilotoResultPage | BalotoResultPage | RevanchaResultPage:
    """Construct the concrete result-page object matching ``game``."""
    match game:
        case "miloto":
            return MilotoResultPage(page, draw_id)
        case "baloto":
            return BalotoResultPage(page, draw_id)
        case "revancha":
            return RevanchaResultPage(page, draw_id)


async def scrape_draw(page: Page, game: Game, draw_id: int) -> GameSchema:
    """
    Navigate to one live draw result page and build its validated schema.

    Performs full navigation and identity validation through
    :meth:`~app.scraper.parsers.base.BasePage.open` — including
    ``UrlValidator``, since this is real navigation rather than an
    injected-HTML test fixture — then extracts every field and returns the
    fully validated schema. The caller is responsible for persisting it
    (see :func:`app.games.repository.save_draw`).

    :param page: Playwright page to navigate (see :func:`app.scraper.playwright_client.get_page`).
    :param game: Which game's result page to scrape.
    :param draw_id: Official draw number to request.
    :return: The validated draw result.
    :raises app.scraper.exceptions.DrawPageNotFoundError: If the requested draw does not
        exist — the site navigated away from the expected URL instead of showing it.
    :raises AssertionError: If a different page-identity or page-structure validator rejects the page.
    :raises ValueError: If a displayed value cannot be parsed.
    :raises pydantic.ValidationError: If the extracted values violate the game's schema constraints.
    """
    result_page = _build_result_page(game, page, draw_id)

    try:
        await result_page.open()
    except AssertionError as error:
        if page.url != result_page.target_url:
            error_message = f"Draw {draw_id} was not found for {game}."
            raise DrawPageNotFoundError(error_message) from error
        raise

    game_id = await result_page.get_game_id()
    game_date = parse_spanish_date(await result_page.get_game_date())
    numbers = await result_page.get_winner_numbers()
    accumulated = await result_page.get_accumulated_prize()
    details = await result_page.get_details()

    if isinstance(result_page, MilotoResultPage):
        return MilotoSchema(
            game_id=game_id,
            game_date=game_date,
            numbers=numbers,
            accumulated=accumulated,
            hits_2=details.get("2"),
            hits_3=details.get("3"),
            hits_4=details.get("4"),
            hits_5=details.get("5"),
        )

    schema_class = BalotoSchema if isinstance(result_page, BalotoResultPage) else RevanchaSchema
    return schema_class(
        game_id=game_id,
        game_date=game_date,
        numbers=numbers,
        accumulated=accumulated,
        super_balota=await result_page.get_balota(),
        hits_3=details.get("3"),
        hits_4=details.get("4"),
        hits_5=details.get("5"),
        hits_sb=details.get("SB"),
        hits_2_sb=details.get("2+SB"),
        hits_3_sb=details.get("3+SB"),
        hits_4_sb=details.get("4+SB"),
        hits_5_sb=details.get("5+SB"),
    )
