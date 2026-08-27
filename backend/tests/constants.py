"""Define shared constants used by the test suite."""

from pathlib import Path

current_dir = Path(__file__).resolve().parent
XPECTED_RESULTS_RESOURCES_DIRECTORY = current_dir / "resources/ex_results"
MOCKED_HTML_RESOURCES_DIRECTORY = current_dir / "resources/html"