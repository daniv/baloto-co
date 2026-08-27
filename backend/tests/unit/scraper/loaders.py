"""
Load complete lottery page test cases from external resources.

This module isolates filesystem access, JSON parsing, mocked HTML loading, and
test-case construction from pytest hooks, fixtures, and Playwright components.
"""

import json
from copy import deepcopy
from typing import TYPE_CHECKING, Any, cast

from tests.unit.scraper.model import GameTestCase, ValidGames

if TYPE_CHECKING:
    from pathlib import Path


_INVALID_HTML_CONTENT = "<html><body></body></html>"


class GameCaseLoader:
    """
    Load complete page-object test cases from JSON and HTML resources.

    The loader receives its resource directories through dependency injection.
    It does not depend on pytest, Playwright, global constants, or stash state.

    :param expected_results_directory: Root directory containing expected-result
        JSON files organized by test module and lottery game.
    :param html_directory: Root directory containing mocked HTML documents.
    """

    def __init__(
        self,
        expected_results_directory: Path,
        html_directory: Path,
    ) -> None:
        """
        Initialize the loader with its external resource directories.

        :param expected_results_directory: Root directory containing the
            expected-result JSON resources.
        :param html_directory: Root directory containing mocked HTML files.
        """
        self._expected_results_directory = expected_results_directory
        self._html_directory = html_directory

    def load(
        self,
        module_name: str,
        game_name: ValidGames,
        expected_key: str,
    ) -> GameTestCase:
        """
        Load and construct one complete lottery page test case.

        :param module_name: Test module directory containing the game JSON file.
        :param game_name: Lottery game associated with the case.
        :param expected_key: JSON key identifying the requested scenario.
        :return: Validated test case containing expectations and HTML content.
        :raises FileNotFoundError: If a required JSON or HTML file is missing.
        :raises LookupError: If the expected scenario is absent from the JSON.
        :raises TypeError: If the external resource structure is invalid.
        """
        json_path = self._expected_results_directory / module_name / f"{game_name}.json"
        available_cases = self._load_json(json_path)
        raw_case = available_cases.get(expected_key)

        if raw_case is None:
            error_message = f"Expected case {expected_key!r} was not found in {json_path}."
            raise LookupError(error_message)

        if not isinstance(raw_case, dict):
            error_message = f"Expected case {expected_key!r} must be a dictionary."
            raise TypeError(error_message)

        case_data = cast("dict[str, Any]", raw_case)
        raw_expected = case_data.get("expected")

        if not isinstance(raw_expected, dict):
            error_message = f"Expected values for case {expected_key!r} must be a dictionary."
            raise TypeError(error_message)

        expected = cast("dict[str, Any]", raw_expected)

        return GameTestCase(
            game_name=game_name,
            json_key=expected_key,
            expected=deepcopy(expected),
            html_content=self._load_html(case_data),
        )

    def _load_html(self, case_data: dict[str, Any]) -> str:
        """
        Load the mocked HTML configured for a test case.

        An absent ``html_file`` represents an intentional invalid-page scenario
        and therefore returns an empty HTML document.

        :param case_data: Raw scenario data loaded from the JSON resource.
        :return: Mocked HTML content or the intentional invalid document.
        :raises FileNotFoundError: If the configured HTML file does not exist.
        :raises TypeError: If ``html_file`` is not a string.
        """
        html_file = case_data.get("html_file")

        if html_file is None:
            return _INVALID_HTML_CONTENT

        if not isinstance(html_file, str):
            error_message = "The 'html_file' value must be a string."
            raise TypeError(error_message)

        html_path = self._html_directory / html_file

        if not html_path.is_file():
            error_message = f"Mocked HTML file not found: {html_path}"
            raise FileNotFoundError(error_message)

        return html_path.read_text(encoding="utf-8")

    @staticmethod
    def _load_json(file_path: Path) -> dict[str, Any]:
        """
        Read and validate a JSON resource containing test scenarios.

        :param file_path: JSON resource to read.
        :return: Mapping of scenario keys to their external test data.
        :raises FileNotFoundError: If the JSON resource does not exist.
        :raises TypeError: If the JSON root is not an object.
        """
        if not file_path.is_file():
            error_message = f"Expected-results file not found: {file_path}"
            raise FileNotFoundError(error_message)

        loaded_data = json.loads(file_path.read_text(encoding="utf-8"))

        if not isinstance(loaded_data, dict):
            error_message = f"JSON root must be an object: {file_path}"
            raise TypeError(error_message)

        return cast("dict[str, Any]", loaded_data)
