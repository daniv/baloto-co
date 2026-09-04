"""
Unit tests for the composable asynchronous page validators.

The file covers the concrete validators used by lottery page objects and the
ordered, atomic validator registry. Validator tests execute against a local
document loaded into a Playwright page; registry tests use recording stubs and
never require a browser.
"""

from typing import TYPE_CHECKING, cast

import pytest
from app.scraper.validators import (
    BalotoImageValidator,
    DrawIdValidator,
    DuplicateValidatorError,
    PageTitleValidator,
    RevanchaImageValidator,
    ValidatorNotRegisteredError,
    ValidatorRegistry,
)

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page


@pytest.mark.asyncio(loop_scope="module")
async def test_page_title_validator(page: Page) -> None:
    """
    Verify that the MiLoto title validator rejects an unexpected page title.

    The test loads a local document with an invalid title and executes the
    validator directly. No external navigation occurs, and the failure is
    isolated from the URL, draw identifier, and metadata validators.
    """
    await page.set_content(
        "<!DOCTYPE html><html><head><title>Baloto</title></head><body></body></html>",
        wait_until="domcontentloaded",
    )
    validator = PageTitleValidator()

    with pytest.raises(AssertionError) as exc_info:
        await validator.validate(page)

    assert "Loaded page title should identify the Miloto game" in str(exc_info.value)


@pytest.mark.asyncio(loop_scope="module")
@pytest.mark.parametrize(
    ("validator_type", "html_content", "expected_message"),
    [
        pytest.param(
            BalotoImageValidator,
            '<html><body data-game="revancha"></body></html>',
            "The loaded page should contain at least one Baloto identity marker",
            id="baloto-rejects-revancha-marker",
        ),
        pytest.param(
            RevanchaImageValidator,
            '<html><body data-game="baloto"></body></html>',
            "The loaded page should contain at least one Revancha identity marker",
            id="revancha-rejects-baloto-marker",
        ),
    ],
)
async def test_image_validator_rejects_the_other_game_marker(
    page: Page,
    validator_type: type[BalotoImageValidator | RevanchaImageValidator],
    html_content: str,
    expected_message: str,
) -> None:
    """
    Verify that each game-image validator rejects the identity marker of the other game.

    The test loads a local document containing only the opposite game's test
    marker. It executes the validator directly, isolating game identity from
    URL, draw identifier, and result extraction behavior.
    """
    await page.set_content(html_content, wait_until="domcontentloaded")
    validator = validator_type()

    with pytest.raises(AssertionError) as exc_info:
        await validator.validate(page)

    assert expected_message in str(exc_info.value)


@pytest.mark.asyncio(loop_scope="module")
async def test_draw_id_validator_rejects_an_unexpected_draw_id(page: Page) -> None:
    """
    Verify that the draw identifier validator rejects a different displayed draw.

    The test loads a local document containing draw 2679 and configures the
    validator to expect draw 2680. The locator factory uses the Playwright page
    received through the validator contract, isolating the validation behavior
    from any concrete Page Object implementation.
    """
    await page.set_content(
        '<html><body><strong id="draw-id">SORTEO #2.679</strong></body></html>',
        wait_until="domcontentloaded",
    )

    def draw_id_locator(current_page: Page) -> Locator:
        return current_page.locator("#draw-id").describe("draw id")

    validator = DrawIdValidator(2680, draw_id_locator)

    with pytest.raises(AssertionError) as exc_info:
        await validator.validate(page)

    assert "Loaded page should display draw 2680" in str(exc_info.value)


class _StubPage:
    """Stand-in Playwright page used when validators ignore the page argument."""


class _RecordingValidator:
    """Record every validation invocation into a shared call log."""

    def __init__(
        self,
        name: str,
        call_log: list[str],
        *,
        fail: bool = False,
    ) -> None:
        self._name = name
        self._call_log = call_log
        self._fail = fail

    @property
    def name(self) -> str:
        """Return the validator registration name."""
        return self._name

    async def validate(self, page: Page) -> None:
        """Append the validator name to the call log and optionally raise."""
        self._call_log.append(self._name)
        if self._fail:
            error_message = f"Validation failed for {self._name!r}."
            raise RuntimeError(error_message)


def _names(registry: ValidatorRegistry) -> tuple[str, ...]:
    """Return the registered validator names in execution order."""
    return tuple(validator.name for validator in registry.validators)


@pytest.mark.unit
def test_init_without_validators_creates_an_empty_registry() -> None:
    """Verify a registry constructed without arguments starts empty."""
    registry = ValidatorRegistry()

    assert registry.validators == ()
    assert registry.has("url") is False


@pytest.mark.unit
def test_init_registers_validators_in_supplied_order() -> None:
    """Verify supplied validators are kept in their given execution order."""
    call_log: list[str] = []
    first = _RecordingValidator("first", call_log)
    second = _RecordingValidator("second", call_log)

    registry = ValidatorRegistry(first, second)

    assert _names(registry) == ("first", "second")


@pytest.mark.unit
def test_init_with_duplicate_names_raises() -> None:
    """Verify construction with duplicated names raises the duplicate error."""
    call_log: list[str] = []
    duplicated = _RecordingValidator("url", call_log)
    other = _RecordingValidator("meta", call_log)

    with pytest.raises(DuplicateValidatorError) as exc_info:
        ValidatorRegistry(duplicated, other, duplicated)

    assert exc_info.value.validator_names == ("url",)
    assert str(exc_info.value) == "Validator names must be unique. Duplicates found: 'url'."


@pytest.mark.unit
def test_has_returns_true_only_for_registered_names() -> None:
    """Verify has() reflects the current registration state."""
    registry = ValidatorRegistry(_RecordingValidator("draw_id", []))

    assert registry.has("draw_id") is True
    assert registry.has("missing") is False


@pytest.mark.unit
def test_register_appends_validators_in_supplied_order() -> None:
    """Verify register() extends the registry preserving the given order."""
    call_log: list[str] = []
    registry = ValidatorRegistry()
    first = _RecordingValidator("first", call_log)
    second = _RecordingValidator("second", call_log)

    registry.register(first, second)

    assert _names(registry) == ("first", "second")


@pytest.mark.unit
def test_register_duplicate_within_call_is_atomic() -> None:
    """Verify a duplicate inside one register() call leaves the registry unchanged."""
    call_log: list[str] = []
    existing = _RecordingValidator("url", call_log)
    registry = ValidatorRegistry(existing)
    duplicated = _RecordingValidator("url", call_log)
    other = _RecordingValidator("meta", call_log)

    with pytest.raises(DuplicateValidatorError) as exc_info:
        registry.register(other, duplicated)

    assert exc_info.value.validator_names == ("url",)
    assert str(exc_info.value) == "Validator names must be unique. Duplicates found: 'url'."
    assert _names(registry) == ("url",)


@pytest.mark.unit
def test_register_duplicate_across_calls_is_atomic() -> None:
    """Verify re-registering an already registered name is rejected."""
    call_log: list[str] = []
    existing = _RecordingValidator("url", call_log)
    registry = ValidatorRegistry(existing)

    with pytest.raises(DuplicateValidatorError) as exc_info:
        registry.register(existing)

    assert exc_info.value.validator_names == ("url",)
    assert _names(registry) == ("url",)


@pytest.mark.unit
def test_register_reports_all_duplicate_names_sorted() -> None:
    """Verify the duplicate error lists every conflicting name in sorted order."""
    call_log: list[str] = []
    registry = ValidatorRegistry(
        _RecordingValidator("url", call_log),
        _RecordingValidator("title", call_log),
    )
    duplicated_url = _RecordingValidator("url", call_log)
    duplicated_title = _RecordingValidator("title", call_log)

    with pytest.raises(DuplicateValidatorError) as exc_info:
        registry.register(duplicated_title, duplicated_url)

    assert exc_info.value.validator_names == ("title", "url")
    assert str(exc_info.value) == "Validator names must be unique. Duplicates found: 'title', 'url'."


@pytest.mark.unit
def test_unregister_returns_and_removes_the_validator() -> None:
    """Verify unregister() returns the removed validator and deletes it."""
    call_log: list[str] = []
    target = _RecordingValidator("draw_id", call_log)
    registry = ValidatorRegistry(target, _RecordingValidator("url", call_log))

    removed = registry.unregister("draw_id")

    assert removed is target
    assert _names(registry) == ("url",)
    assert registry.has("draw_id") is False


@pytest.mark.unit
def test_unregister_unknown_name_raises() -> None:
    """Verify unregistering an absent name raises the dedicated error."""
    registry = ValidatorRegistry(_RecordingValidator("url", []))

    with pytest.raises(ValidatorNotRegisteredError) as exc_info:
        registry.unregister("missing")

    assert exc_info.value.validator_name == "missing"
    assert str(exc_info.value) == "Validator 'missing' is not registered."


@pytest.mark.unit
def test_unregister_all_returns_validators_in_registration_order() -> None:
    """Verify unregister_all() returns every validator and empties the registry."""
    call_log: list[str] = []
    first = _RecordingValidator("first", call_log)
    second = _RecordingValidator("second", call_log)
    registry = ValidatorRegistry(first, second)

    removed = registry.unregister_all()

    assert removed == (first, second)
    assert registry.validators == ()


@pytest.mark.unit
async def test_validate_invokes_every_registered_validator_in_order() -> None:
    """Verify validate() runs each validator exactly once in registration order."""
    call_log: list[str] = []
    registry = ValidatorRegistry(
        _RecordingValidator("first", call_log),
        _RecordingValidator("second", call_log),
        _RecordingValidator("third", call_log),
    )
    page = cast("Page", _StubPage())

    await registry.validate(page)

    assert call_log == ["first", "second", "third"]


@pytest.mark.unit
async def test_validate_stops_at_the_first_failing_validator() -> None:
    """Verify validate() aborts and propagates the first validator exception."""
    call_log: list[str] = []
    registry = ValidatorRegistry(
        _RecordingValidator("first", call_log),
        _RecordingValidator("failing", call_log, fail=True),
        _RecordingValidator("never", call_log),
    )
    page = cast("Page", _StubPage())

    with pytest.raises(RuntimeError, match=r"Validation failed for 'failing'\."):
        await registry.validate(page)

    assert call_log == ["first", "failing"]
