"""
Shared pytest fixtures for database-backed tests.

Provides a real, disposable PostgreSQL instance via Testcontainers, an
async SQLAlchemy engine bound to it, and a per-test isolated session
that rolls back after each test so no test leaks data into the next one.
"""

import pytest
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Generator

GAMES_LIST: tuple[str, ...] = ("miloto", "baloto", "revancha")

# region Pytest hooks

@pytest.hookimpl
def pytest_addoption(parser: pytest.Parser) -> None:
    """
    Add command-line options for pytest.

    :param parser: Pytest command-line parser.
    :return: None
    """
    group = parser.getgroup("baloto-generator", "Baloto Generator custom options")
    group.addoption(
        "--game",
        action="store",
        default=None,
        choices=["miloto", "baloto", "revancha"],
        help="Run tests on the specified game. Options: miloto, baloto, revancha.",
    )

@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    """
    Register the custom pytest markers used by page-object tests.

    :param config: Active pytest configuration object.
    :return: None.
    """
    config.addinivalue_line("markers", "skip_game(name): mark test to be skipped a specific game")
    config.addinivalue_line("markers", "only_game(name): mark test to run only on a specific game")
    config.addinivalue_line("markers", "crossgames: runs the test on all games engines (miloto, baloto and revancha)")


# endregion
