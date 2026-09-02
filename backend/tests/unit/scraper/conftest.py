"""
Configure cross-game page-object tests and their shared infrastructure.

This module coordinates game parametrization, external test resources,
Playwright lifecycle management, and lottery result-page construction.

The architecture separates the test workflow into the following concerns:

* Select the lottery games applicable to each test through ``crossgames``,
  ``only_game``, ``skip_game``, and the ``--game`` command-line option.
* Generate only the required game-specific test cases during collection.
* Represent each scenario as an immutable ``GameTestCase`` containing the
  selected game, expected-result key, expected values, and HTML content.
* Load expected-result JSON files and mocked HTML through ``GameCaseLoader``.
* Provide one Playwright browser context shared by the test module.
* Create an isolated empty Playwright page for each test execution.
* Load the active case HTML through the dedicated ``case_page`` fixture.
* Provide an independent mutable copy of expected values through
  ``expected_result``.
* Construct the result-page implementation associated with the active game.

The execution flow is:

1. ``pytest_generate_tests`` determines the games that must be executed.
2. ``GameCaseLoader`` loads the expected values and mocked HTML resources.
3. ``game_case`` exposes the validated immutable ``GameTestCase``.
4. ``page`` creates an isolated empty Playwright page.
5. ``case_page`` loads ``game_case.html_content`` into that page.
6. ``result_page_factory`` creates the game-specific implementation using the
   Playwright page selected by the test.
7. ``expected_result`` exposes a mutable deep copy of the expected values.
8. The test compares the page-object result with its expected result.

The design follows the SOLID principles:

* Single Responsibility Principle:
  game selection, resource loading, browser management, page lifecycle, HTML
  loading, expected-result copying, and page-object construction are handled
  by separate components.
* Open/Closed Principle:
  additional games and test scenarios can be introduced without changing the
  resource-loading and browser-management workflow.
* Liskov Substitution Principle:
  every supported result-page implementation can be consumed through the
  common ``ResultPage`` contract.
* Interface Segregation Principle:
  fixtures and tests receive only the data and dependencies they require.
* Dependency Inversion Principle:
  test infrastructure depends on explicit case, loader, and factory
  abstractions instead of loading external resources directly inside tests.
"""

from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio
from app.scraper import BalotoResultPage, MilotoResultPage, RevanchaResultPage
from playwright.async_api import async_playwright

from tests.constants import (
    MOCKED_HTML_RESOURCES_DIRECTORY,
    XPECTED_RESULTS_RESOURCES_DIRECTORY,
)
from tests.pytest_utils import get_skiplist
from tests.unit.scraper.loaders import GameCaseLoader

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

    from app.scraper import ResultPage
    from playwright.async_api import BrowserContext, Page

    from tests.unit.scraper.model import GameTestCase, ValidGames


GAMES_LIST: list[ValidGames] = ["miloto", "baloto", "revancha"]


# region Pytest hooks


@pytest.hookimpl
def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """
    Parametrize a test with the games selected through pytest markers.

    The supported selection strategies are:

    * ``crossgames``: execute the test for every supported game.
    * ``only_game(name)``: execute the test only for the selected game.
    * ``skip_game(name)``: execute the test for every game except the selected
      game.

    The ``--game`` command-line option is applied after the marker selection
    and therefore acts as the final execution filter.

    :param metafunc: Pytest metadata for the test function being collected.
    :return: None.
    """
    game_markers = ("crossgames", "only_game", "skip_game")
    has_game_marker = any(
        metafunc.definition.get_closest_marker(marker_name) is not None for marker_name in game_markers
    )

    if not has_game_marker:
        return

    skip_games = get_skiplist(metafunc.definition, GAMES_LIST, "game")
    games_to_execute = [game for game in GAMES_LIST if game not in skip_games]

    cli_game: ValidGames | None = metafunc.config.getoption("--game")
    if cli_game is not None:
        games_to_execute = [cli_game] if cli_game in games_to_execute else []

    metafunc.parametrize("game_name", games_to_execute, scope="function")


# endregion


# region Module scoped fixtures


@pytest.fixture(scope="session")
def game_case_loader() -> GameCaseLoader:
    """
    Provide the resource loader shared by the entire pytest session.

    The fixture acts as the composition root for the loader by injecting the
    expected-results and mocked-HTML directories required by the test suite.

    :return: Loader configured with the page-test resource directories.
    """
    return GameCaseLoader(
        expected_results_directory=XPECTED_RESULTS_RESOURCES_DIRECTORY,
        html_directory=MOCKED_HTML_RESOURCES_DIRECTORY,
    )


@pytest.fixture
def game_case(
    request: pytest.FixtureRequest,
    game_name: ValidGames,
    expected_key: str,
    game_case_loader: GameCaseLoader,
) -> GameTestCase:
    """
    Provide the complete test case for the active game and scenario.

    The fixture adapts pytest parametrization to the resource loader. Missing
    external resources cause the affected parametrized case to be skipped,
    while structurally invalid resources remain test-configuration errors.

    :param request: Fixture request associated with the active test.
    :param game_name: Lottery game selected for the current test case.
    :param expected_key: JSON key identifying the active scenario.
    :param game_case_loader: Loader configured with the resource directories.
    :return: Complete validated lottery page test case.
    """
    node = getattr(request, "node", None)
    if not isinstance(node, pytest.Item):
        error_message = "The active fixture request is not associated with a pytest item."
        raise TypeError(error_message)

    module_name = Path(node.location[0]).resolve().stem

    try:
        return game_case_loader.load(
            module_name=module_name,
            game_name=game_name,
            expected_key=expected_key,
        )
    except (FileNotFoundError, LookupError) as error:
        pytest.skip(reason=str(error))


@pytest.fixture(scope="session")
def game_name(pytestconfig: pytest.Config) -> ValidGames:
    """
    Return the game selected through the command line.

    :param pytestconfig: Active pytest configuration.
    :return: Selected game, defaulting to MiLoto.
    """
    cli_game: ValidGames | None = pytestconfig.getoption("--game")
    return cli_game or "miloto"


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def browser_context() -> AsyncGenerator[BrowserContext]:
    """
    Provide one browser context shared by all page tests in the module.

    Playwright, Chromium, and the browser context are initialized together
    and released in reverse order after every test in the module completes.

    :return: Shared browser context used to create isolated test pages.
    """
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="es-CO",
            offline=True,
            java_script_enabled=False,
            strict_selectors=True,
        )

        yield context

        await context.close()
        await browser.close()


@pytest_asyncio.fixture(loop_scope="module")
async def page(browser_context: BrowserContext) -> AsyncGenerator[Page]:
    """
    Provide an isolated empty Playwright page.

    The fixture manages only the page lifecycle. It does not load test data,
    expected results, or mocked HTML resources.

    :param browser_context: Browser context shared by the test module.
    :return: Empty Playwright page for the active test.
    """
    test_page = await browser_context.new_page()

    try:
        yield test_page
    finally:
        await test_page.close()


@pytest_asyncio.fixture(loop_scope="module")
async def case_page(page: Page, game_case: GameTestCase) -> Page:
    """
    Load the active test-case HTML into an isolated Playwright page.

    :param page: Empty Playwright page created for the active test.
    :param game_case: Complete prepared lottery test case.
    :return: Page containing the mocked HTML associated with the case.
    """
    await page.set_content(
        game_case.html_content,
        wait_until="domcontentloaded",
    )
    return page


@pytest_asyncio.fixture(name="mocked_url", loop_scope="module")
async def identity_page(
    page: Page,
    game_case: GameTestCase,
    result_page_factory: Callable[[Page, int], ResultPage],
) -> ResultPage:
    """
    Provide a result page loaded through its expected public URL.

    The fixture creates the Page Object for the active parametrized game,
    intercepts its ``target_url``, fulfills the navigation with the local HTML
    fixture, and navigates directly with Playwright without calling ``open()``.

    :param page: Empty Playwright page created for the active test.
    :param game_case: Complete lottery test case containing HTML and expected data.
    :param result_page_factory: Factory for the active lottery Page Object.
    :return: Page Object bound to the mocked document and realistic game URL.
    :raises TypeError: If the test case does not define an integer ``draw_id``.
    """
    draw_id = game_case.expected.get("draw_id")
    if not isinstance(draw_id, int):
        error_message = "The identity test case requires an integer draw_id."
        raise TypeError(error_message)

    result_page = result_page_factory(page, draw_id)

    await page.route(
        result_page.target_url,
        lambda route: route.fulfill(
            status=200,
            content_type="text/html",
            body=game_case.html_content,
        ),
    )
    await page.goto(
        result_page.target_url,
        wait_until="domcontentloaded",
    )

    return result_page


@pytest.fixture
def result_page_factory(game_name: ValidGames) -> Callable[[Page, int], ResultPage]:
    """
    Create a result-page object using a page selected by the test.

    The factory determines the concrete result-page implementation from the
    active parametrized game, while the test remains responsible for choosing
    the Playwright page and its HTML content.

    :param game_name: Lottery game selected for the current parametrized case.
    :return: Factory receiving a Playwright page and draw identifier.
    """

    def _create_result_page(page: Page, draw_id: int) -> ResultPage:
        match game_name:
            case "miloto":
                return MilotoResultPage(page, draw_id)
            case "baloto":
                return BalotoResultPage(page, draw_id)
            case "revancha":
                return RevanchaResultPage(page, draw_id)
            case _:
                error_message = f"Unsupported game name: {game_name}"
                raise ValueError(error_message)

    return _create_result_page


@pytest.fixture
def expected_result(game_case: GameTestCase) -> dict[str, Any]:
    """
    Provide an independent mutable copy of the expected test result.

    The deep copy allows each test to alter nested expected values without
    modifying the immutable base case or contaminating other parametrized
    executions.

    :param game_case: Complete base test case loaded from external resources.
    :return: Mutable deep copy of the expected result.
    """
    return deepcopy(game_case.expected)


# endregion
