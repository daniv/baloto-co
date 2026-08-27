"""
Test page-object extraction against intentionally corrupted result documents.

The module locks in the error behavior production callers receive when the
draw date is missing or does not match the expected text pattern. Each test
loads a pristine or corrupted case through the loader and asserts the
existing ``AssertionError`` raised by the page object. Schema-level date
validation is covered by the schema test suite and is not exercised here.
"""

from typing import TYPE_CHECKING, cast

import pytest

from backend.app.scraper.parsers.baloto import BalotoResultPage

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.scraper import ResultPage
    from playwright.async_api import Page
    from tests.unit.scraper.loaders import GameCaseLoader
    from tests.unit.scraper.model import ValidGames

async def shared_missing_data_loader(
    page: Page,
    result_page_factory: Callable[[Page, int], ResultPage],
    game_case_loader: GameCaseLoader, 
          game_name: ValidGames,
          key: str
) -> ResultPage:
    game_case = game_case_loader.load(
        module_name="tests_pages",
        game_name=game_name,
        expected_key=key,
    )
    await page.set_content(
        game_case.html_content,
        wait_until="domcontentloaded",
    )
    return result_page_factory(page, game_case.expected["game_id"])


@pytest.mark.skip_game("revancha")
@pytest.mark.asyncio(loop_scope="module")
async def test_missing_date_raises(
    game_name: ValidGames,
    game_case_loader: GameCaseLoader,
    page: Page,
    result_page_factory: Callable[[Page, int], ResultPage],
) -> None:
    """Verify that a result document without a draw date raises an AssertionError."""

    result_page = await shared_missing_data_loader(
        page, result_page_factory, game_case_loader, game_name, "missing_date"
    )

    with pytest.raises(AssertionError, match="draw date should contain exactly 1 node"):
        await result_page.get_game_date()


@pytest.mark.skip_game("revancha")
@pytest.mark.asyncio(loop_scope="module")
async def test_invalid_date_format_raises(
    game_name: ValidGames,
    game_case_loader: GameCaseLoader,
    page: Page,
    result_page_factory: Callable[[Page, int], ResultPage],
) -> None:
    """Verify that a date not matching the expected text pattern raises an error."""
    game_case = game_case_loader.load(
        module_name="tests_pages",
        game_name=game_name,
        expected_key="jackpot",
    )

    # The expected date value is replaced in memory with a non-matching format before the page loads the document
    pristine_date = game_case.expected["game_date"]
    assert pristine_date in game_case.html_content, (
        f"The expected date {pristine_date!r} is not present in the fixture "
        "HTML; the in-memory replacement would silently do nothing."
    )
    damaged_html = game_case.html_content.replace(pristine_date, "23/07/2026")

    await page.set_content(
        damaged_html,
        wait_until="domcontentloaded",
    )

    result_page = result_page_factory(page, game_case.expected["game_id"])

    with pytest.raises(AssertionError, match="draw date should contain exactly 1 node"):
        await result_page.get_game_date()


@pytest.mark.skip_game("revancha")
@pytest.mark.asyncio(loop_scope="module")
async def test_missing_accumulated_raises(
    game_name: ValidGames,
    game_case_loader: GameCaseLoader,
    page: Page,
    result_page_factory: Callable[[Page, int], ResultPage],
) -> None:
    """
    Verify that a result document without a draw accumulated raises an AssertionError."""
    result_page = await shared_missing_data_loader(
        page, result_page_factory, game_case_loader, game_name, "missing_accumulated"
    )

    try:
        await result_page.get_accumulated_prize()
    except Exception as e:
        print(str(e))
    with pytest.raises(AssertionError, match="accumulated prize should contain exactly 1 node"):
        await result_page.get_accumulated_prize()

@pytest.mark.only_game("miloto")
@pytest.mark.asyncio(loop_scope="module")
@pytest.mark.parametrize("text, replace", [
        pytest.param("ACUMULADO DEL SORTEO", "", id="no_title"),
        pytest.param("$230 MILLONES", "100", id="invalid_format"),
        pytest.param("$230 MILLONES", "-$230 MILLONES", id="negative"),
    ]
)
async def test_invalid_accumulated_format_raises(
    game_name: ValidGames,
    game_case_loader: GameCaseLoader,
    page: Page,
    result_page_factory: Callable[[Page, int], ResultPage],
    text: str, replace: str
) -> None:
    """Verify that the accumulated not matching the expected text pattern raises an error."""

    game_case = game_case_loader.load(
        module_name="tests_pages",
        game_name=game_name,
        expected_key="jackpot",
    )

    # The expected date value is replaced in memory with a non-matching format before the page loads the document
    assert text in game_case.html_content, (
        f"The expected phrase {text!r} is not present in the fixture "
        "HTML; the in-memory replacement would silently do nothing."
    )
    damaged_html = game_case.html_content.replace(text, replace)
    
    await page.set_content(
        damaged_html,
        wait_until="domcontentloaded",
    )

    result_page = result_page_factory(page, game_case.expected["game_id"])

    with pytest.raises(AssertionError, match="accumulated prize should contain exactly 1 node"):
        await result_page.get_accumulated_prize()

@pytest.mark.only_game("baloto")
@pytest.mark.asyncio(loop_scope="module")
async def test_missing_sb_result(
    game_name: ValidGames,
    game_case_loader: GameCaseLoader,
    page: Page,
    result_page_factory: Callable[[Page, int], ResultPage]
) -> None:
    """
    Verify that a result document without a super-balota result raises an AssertionError."""
    result_page = await shared_missing_data_loader(
        page, result_page_factory, game_case_loader, game_name, "no_sb"
    )

    with pytest.raises(AssertionError, match="balota should contain exactly 1 node"):
        result_page = cast(BalotoResultPage, result_page)
        await result_page.get_balota()