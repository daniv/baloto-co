"""
Test the page-object validators and ``open()`` navigation behavior.

The suite covers field-level validation of the ``ResultPage`` page objects and the
validator-registry rejections raised during ``open()`` (wrong final URL, invalid
navigation response, and browser-offline failures), plus ``draw_id`` validation.
"""

from typing import TYPE_CHECKING, Any, cast

import pytest
from app.scraper import BalotoResultPage, MilotoResultPage, RevanchaResultPage
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page, Response

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.scraper import ResultPage
    from playwright.async_api import Page
    from pytest_mock import MockerFixture

    from tests.unit.scraper.conftest import (
        case_page,
        expected_result,
        game_name,
        result_page_factory,
    )
    from tests.unit.scraper.model import ValidGames

    _FIXTURE_IMPORTS: tuple[object, ...] = (
        case_page,
        expected_result,
        game_name,
        result_page_factory,
    )


@pytest.mark.crossgames
@pytest.mark.asyncio(loop_scope="module")
@pytest.mark.parametrize("expected_key", ["no_jackpot", "jackpot"])
async def test_validate_all_fields(
    game_name: ValidGames,
    expected_result: dict[str, Any],
    case_page: Page,
    result_page_factory: Callable[[Page, int], ResultPage],
    expected_key: str,
) -> None:
    """
    Validate the complete extraction behavior for every lottery result page.

    The test loads the mocked HTML associated with each game and scenario,
    creates the corresponding result-page object, and verifies every expected
    field extracted from the document.
    """
    expected = expected_result.copy()
    game_id = expected.pop("game_id")
    expected_game_date = expected.pop("game_date")
    expected_winner_numbers = expected.pop("winner_numbers")
    expected_accumulated_prize = expected.pop("accumulated_prize")
    expected_details = expected.pop("details")

    result_page = result_page_factory(case_page, game_id)

    game_display_name = game_name.capitalize()
    hits = ("SB", "2+SB", "3", "3+SB", "4", "5", "5+SB")
    if game_name == "miloto":
        hits = ("2", "3", "4", "5")

    if game_name != "miloto":
        expected_balota = expected.pop("balota")
        br_page = (
            cast("BalotoResultPage", result_page) if game_name == "baloto" else cast("RevanchaResultPage", result_page)
        )
        actual_balota = await br_page.get_balota()

        assert actual_balota == expected_balota, (
            f"Unexpected balota for game={game_name!r}, "
            f"case={expected_key!r}. "
            f"Expected: {expected_balota!r}. "
            f"Actual: {actual_balota!r}."
        )

    actual_game_id = await result_page.get_game_id()
    assert actual_game_id == game_id, (
        f"Unexpected game identifier for game={game_name!r}, "
        f"case={expected_key!r}. "
        f"Expected: {game_id!r}. "
        f"Actual: {actual_game_id!r}."
    )

    actual_game_date = await result_page.get_game_date()
    assert actual_game_date == expected_game_date, (
        f"Unexpected game date for game={game_name!r}, "
        f"case={expected_key!r}. "
        f"Expected: {expected_game_date!r}. "
        f"Actual: {actual_game_date!r}."
    )

    actual_winner_numbers = await result_page.get_winner_numbers()
    assert actual_winner_numbers == expected_winner_numbers, (
        f"Unexpected winner numbers for game={game_name!r}, "
        f"case={expected_key!r}. "
        f"Expected: {expected_winner_numbers!r}. "
        f"Actual: {actual_winner_numbers!r}."
    )

    actual_accumulated_prize = await result_page.get_accumulated_prize()
    assert actual_accumulated_prize == expected_accumulated_prize, (
        f"Unexpected accumulated prize for game={game_name!r}, "
        f"case={expected_key!r}. "
        f"Expected: {expected_accumulated_prize!r}. "
        f"Actual: {actual_accumulated_prize!r}."
    )

    actual_details = await result_page.get_details()

    for hit in hits:
        detail_key = f"hits_{hit.lower().replace('+', '_')}"
        actual_detail = actual_details.get(hit)

        if detail_key not in expected_details:
            assert actual_detail is None, (
                f"Unexpected payout category for game={game_name!r}, "
                f"case={expected_key!r}, category={hit!r}. "
                f"Actual: {actual_detail!r}."
            )
            continue

        expected_detail = expected_details[detail_key]

        assert actual_detail is not None, (
            f"Missing payout category for game={game_name!r}, "
            f"case={expected_key!r}, category={hit!r}. "
            f"Expected: {expected_detail!r}."
        )

        assert actual_detail.winners == expected_detail["winners"], (
            f"Unexpected winner count for {game_display_name} "
            f"case={expected_key!r}, category={hit!r}. "
            f"Expected: {expected_detail['winners']!r}. "
            f"Actual: {actual_detail.winners!r}."
        )

        assert actual_detail.prize_for_winner == expected_detail["prize_for_winner"], (
            f"Unexpected prize per winner for {game_display_name} "
            f"case={expected_key!r}, category={hit!r}. "
            f"Expected: {expected_detail['prize_for_winner']!r}. "
            f"Actual: {actual_detail.prize_for_winner!r}."
        )

    assert not expected, (
        f"Expected fields were not validated for game={game_name!r}, case={expected_key!r}: {sorted(expected)}."
    )


@pytest.mark.crossgames
def test_validate_page_init_fail_invalid_drawid(game_name: ValidGames, page: Page) -> None:
    """Validate that an invalid draw identifier is rejected during initialization."""
    match game_name:
        case "miloto":
            with pytest.raises(ValueError, match="draw_id must be greater"):
                MilotoResultPage(page, 0)
        case "baloto":
            with pytest.raises(ValueError, match="draw_id must be greater"):
                BalotoResultPage(page, 0)
        case "revancha":
            with pytest.raises(ValueError, match="draw_id must be greater"):
                RevanchaResultPage(page, 0)


@pytest.mark.crossgames
@pytest.mark.asyncio(loop_scope="module")
async def test_open_rejects_an_incorrect_final_url(
    page: Page,
    result_page_factory: Callable[[Page, int], ResultPage],
    mocker: MockerFixture,
) -> None:
    """
    Verify that ``open()`` rejects a page whose final URL differs from ``target_url``.

    The test replaces ``page.goto()`` with an asynchronous mock that returns a
    successful Playwright response without performing a real network request.
    Because the page remains at ``about:blank``, the registered ``UrlValidator``
    must raise an ``AssertionError`` when ``open()`` validates the final URL.

    :param page: Empty Playwright page created for the active test.
    :param result_page_factory: Factory for the active parametrized result-page implementation.
    :param mocker: Pytest-mock fixture used to create and restore the asynchronous navigation mock.
    """
    result_page = result_page_factory(page, 1)
    response = mocker.MagicMock(spec=Response)
    response.ok = True

    mocker.patch.object(page, "goto", new=mocker.AsyncMock(return_value=response))

    with pytest.raises(AssertionError) as exc_info:
        await result_page.open()

    expected_message = f"Loaded page URL should match {result_page.target_url!r}"
    assert expected_message in str(exc_info.value)


@pytest.mark.asyncio(loop_scope="module")
@pytest.mark.parametrize("err_type", ["response_none", "response_notok"])
async def test_open_rejects_an_invalid_navigation_response(page: Page, mocker: MockerFixture, err_type: str) -> None:
    """
    Verify that ``open()`` rejects missing and unsuccessful navigation responses.

    The test replaces ``page.goto()`` with an asynchronous mock, preventing
    external network traffic while exercising both HTTP-response guard clauses
    implemented by ``BasePage.open()``.
    """
    result_page = MilotoResultPage(page, 1)

    if err_type == "response_none":
        mocked_response = None
        expected_message = f"Navigation to {result_page.target_url} produced no response."
    else:
        response = mocker.MagicMock(spec=Response)
        response.ok = False
        response.status = 503
        response.url = result_page.target_url
        mocked_response = response
        expected_message = f"{result_page.game_name} returned HTTP 503 for {result_page.target_url}."

    mocker.patch.object(page, "goto", new=mocker.AsyncMock(return_value=mocked_response))

    with pytest.raises(RuntimeError) as exc_info:
        await result_page.open()

    assert str(exc_info.value) == expected_message


@pytest.mark.asyncio(loop_scope="module")
async def test_open_raises_playwright_error_when_browser_offline(page: Page) -> None:
    """
    Verify that ``open()`` propagates Playwright's offline navigation error.

    The browser context is configured with ``offline=True``, so navigation
    fails before ``page.goto()`` can return a Playwright ``Response``.
    """
    miloto_page = MilotoResultPage(page, 1)

    with pytest.raises(PlaywrightError) as exc_info:
        await miloto_page.open()

    assert "ERR_INTERNET_DISCONNECTED" in str(exc_info.value)
