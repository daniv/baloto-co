"""
Define validated data structures for lottery page-object test cases.

The models in this module represent prepared test data independently from
pytest hooks, fixtures, filesystem access, and Playwright infrastructure.
"""

from typing import Any, Literal

from pydantic import ConfigDict
from pydantic.dataclasses import dataclass

type ValidGames = Literal["miloto", "baloto", "revancha"]


@dataclass(
    frozen=True,
    slots=True,
    config=ConfigDict(extra="forbid"),
)
class GameTestCase:
    """
    Represent all prepared data required to execute one lottery page test.

    The instance combines the selected lottery game, the expected scenario,
    its assertion data, and the HTML document that will be injected into an
    isolated Playwright page.

    :param game_name: Lottery game associated with the test case.
    :param json_key: JSON key identifying the expected scenario.
    :param expected: Expected values consumed by test assertions.
    :param html_content: Mocked HTML injected into the Playwright page.
    """

    game_name: ValidGames
    json_key: str
    expected: dict[str, Any]
    html_content: str
