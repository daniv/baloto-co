"""
Provide asynchronous extraction and validation for Baloto and Revancha draw results.

The module defines ``BalotoRevanchaResultPage``, the shared extraction implementation
for the two games' identical result-page structure, and its concrete ``BalotoResultPage``
and ``RevanchaResultPage`` subclasses, which only differ in result URL and page-identity
markers.
"""

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, get_args

from pydantic import TypeAdapter

from app.core.config import settings
from app.games.schemas import ResultDetails
from app.scraper.parsers.base import (
    BasePage,
    extract_detail_integer,
    get_inner_text,
    get_required_text,
    require_exact_count,
)
from app.scraper.validators import BalotoImageValidator, DrawIdValidator, RevanchaImageValidator
from app.shared.math_utils import es_localized_to_int, parse_millions_to_pesos

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page
    from pydantic import HttpUrl


type BalotoHits = Literal["SB", "2+SB", "3", "3+SB", "4", "4+SB", "5", "5+SB"]


@dataclass(frozen=True, slots=True)
class DetailsColumnIndexes:
    """
    Store resolved indexes for required payout-table columns.

    The immutable value object records the positions of the hit category, winner
    count, and prize-per-winner columns after the table header has been validated.
    """

    hits: int
    winners: int
    prize_for_winner: int


class BalotoRevanchaResultPage(BasePage):
    """
    Represent and validate an individual Baloto draw result page.

    The page object reuses the shared Baloto/Revancha extraction implementation,
    configures the Baloto result URL, and registers validators for the Baloto page
    identity and expected draw identifier.
    """

    _DETAILS_COUNT = 8
    _DETAILS_COLUMN_COUNT = 4
    _RESULT_CONTAINER_SELECTOR = "#balotoBgNew"
    _BALOTO_HITS_ADAPTER: TypeAdapter[BalotoHits] = TypeAdapter(BalotoHits)

    # region Pattern Members

    _EXPECTED_HITS: frozenset[BalotoHits] = frozenset(get_args(BalotoHits.__value__))
    _GAME_ID_PATTERN = re.compile(r"^SORTEO\s+(\d{1,3}(?:\.\d{3})*)$", re.IGNORECASE)
    _GAME_DATE_PATTERN = re.compile(
        r"^\s*\d{1,2}\s+de\s+[A-Za-zÁÉÍÓÚáéíóúÑñ]+\s+de\s+\d{4}\s*$",
        re.IGNORECASE,
    )
    _ACCUMULATED_PRIZE_PATTERN = re.compile(
        r"^\s*ACUMULADO DEL SORTEO:\s*\$([\d.]+)\s+MILLONES\s*$",
        re.IGNORECASE,
    )

    # endregion

    def __init__(self, page: Page, draw_id: int) -> None:
        """
        Initialize shared Baloto/Revancha extraction for a specific draw.

        The constructor delegates common page, URL, draw-identifier, and validator
        registry initialization to ``BasePage``. Concrete subclasses subsequently
        register their game-specific identity and draw validators.

        :param page: Playwright page used to navigate and extract the result document.
        :param draw_id: Positive Baloto-style draw identifier expected in the loaded page.
        :raises ValueError: If ``draw_id`` is not greater than zero.
        """
        super().__init__(page, draw_id)

    # region Locators

    @classmethod
    def _game_id(cls, page: Page) -> Locator:
        """Return the locator containing the Baloto-style draw identifier."""
        has_text = re.compile(r"\bSORTEO\b", re.IGNORECASE)
        return (
            page.locator(cls._RESULT_CONTAINER_SELECTOR).locator("strong").filter(has_text=has_text).describe("game id")
        )

    def _result_container(self) -> Locator:
        return self._page.locator(self._RESULT_CONTAINER_SELECTOR).describe("container balotoBgNew")

    def _game_date(self) -> Locator:
        """Return the locator containing the Baloto-style draw date."""
        return (
            self._result_container()
            .locator("div.gotham-medium.dark-blue")
            .filter(has_text=self._GAME_DATE_PATTERN)
            .describe("game date")
        )

    def _accumulated_prize(self) -> Locator:
        """Return the locator containing the accumulated draw prize."""
        return self._result_container().get_by_text(self._ACCUMULATED_PRIZE_PATTERN).describe("Accumulated prize")

    def _winner_numbers(self) -> Locator:
        """
        Return the five regular winning-number locators.

        The locator is scoped to yellow result balls so the red superball is excluded.
        """
        return self._result_container().locator(".container-balls-results .yellow-ball").describe("Winner numbers")

    def _balota(self) -> Locator:
        """Return the locator containing the red superball."""
        return self._result_container().locator(".container-balls-results .red-ball").describe("balota")

    def _details_container(self) -> Locator:
        """Return the locator containing the payout table."""
        return self._result_container().locator(".table-responsive")

    def _details_header_row(self) -> Locator:
        """Return the payout-table header-row locator."""
        return self._details_container().locator("thead tr")

    def _detail_rows(self) -> Locator:
        """Return the payout-table category-row locator."""
        return self._details_container().locator("tbody tr")

    # endregion

    # region Service Protected Methods

    def _validate_hits(self, hits: str) -> BalotoHits:
        """
        Validate and narrow a Baloto-style hit category.

        :param hits: Category text to normalize and validate.
        :return: Supported typed Baloto hit category.
        :raises ValueError: If the normalized category is unsupported.
        """
        normalized_hits = re.sub(r"\s+", "", hits).upper()
        return self._BALOTO_HITS_ADAPTER.validate_python(normalized_hits)

    async def _get_validated_detail_rows(self) -> list[Locator]:
        """
        Return the complete validated payout-row collection.

        :return: Eight locators representing the expected Baloto-style hit categories.
        :raises AssertionError: If the result document does not contain exactly eight rows.
        """
        rows_locator = self._detail_rows()
        await require_exact_count(rows_locator, self._DETAILS_COUNT, "prize-category rows")

        return await rows_locator.all()

    async def _get_detail_category(self, row: Locator, indexes: DetailsColumnIndexes) -> BalotoHits:
        """
        Extract and validate the hit category from a payout-table row.

        :param row: Payout-table row locator.
        :param indexes: Resolved indexes for the required table columns.
        :return: Validated Baloto-style hit category.
        :raises AssertionError: If the row does not contain the expected number of cells.
        :raises ValueError: If the displayed category is unsupported.
        """
        cells = row.locator("td")
        await require_exact_count(cells, self._DETAILS_COLUMN_COUNT, "prize-table row cells")
        category_text = await get_inner_text(
            cells.nth(indexes.hits),
        )
        normalized_category = _normalize_baloto_hits_key(category_text)

        return self._validate_hits(normalized_category)

    async def _get_details_column_indexes(self) -> DetailsColumnIndexes:
        """
        Resolve required payout-table columns from the displayed headers.

        :return: Indexes for the hit, winner-count, and prize-per-winner columns.
        :raises AssertionError: If the header row or columns do not have the expected count.
        :raises ValueError: If one or more required column headers are missing.
        """
        header_row = self._details_header_row()
        await require_exact_count(header_row, 1, "prize-table header row")

        header_cells = header_row.locator("th")
        await require_exact_count(header_cells, self._DETAILS_COLUMN_COUNT, "prize-table header columns")

        headers = await header_cells.all_inner_texts()
        normalized_headers = [re.sub(r"\s+", " ", header).strip().upper() for header in headers]

        required_headers = {
            "ACIERTOS",
            "GANADORES",
            "PREMIO POR GANADOR",
        }
        missing_headers = required_headers.difference(normalized_headers)

        if missing_headers:
            missing_columns = ", ".join(sorted(missing_headers))
            error_message = f"The Baloto-style prize table is missing required columns: {missing_columns}."
            raise ValueError(error_message)

        return DetailsColumnIndexes(
            hits=normalized_headers.index("ACIERTOS"),
            winners=normalized_headers.index("GANADORES"),
            prize_for_winner=normalized_headers.index("PREMIO POR GANADOR"),
        )

    async def _parse_detail_row(self, row: Locator, indexes: DetailsColumnIndexes) -> ResultDetails | None:
        """
        Parse one validated Baloto-style payout-table row.

        :param row: Payout-table row locator to parse.
        :param indexes: Resolved indexes for the required table columns.
        :return: Category and payout details, or ``None`` when the category has no winners.
        :raises AssertionError: If the row does not contain the expected number of cells.
        :raises ValueError: If the category or a numeric payout value is invalid.
        """
        cells = row.locator("td")
        winners_text = await get_inner_text(cells.nth(indexes.winners))
        winners = extract_detail_integer(winners_text, "GANADORES", self.game_name)

        if winners == 0:
            return None

        prize_text = await get_inner_text(cells.nth(indexes.prize_for_winner))
        prize_for_winner = extract_detail_integer(prize_text, "PREMIO POR GANADOR", self.game_name)

        return ResultDetails(
            prize_for_winner=prize_for_winner,
            winners=winners,
        )

    # endregion

    async def get_details(self) -> dict[str, ResultDetails]:
        """
        Extract payout information for every Baloto-style hit category.

        All eight expected categories are validated. Categories with no winners are
        omitted from the returned mapping after their presence has been confirmed.

        :return: Mapping of hit categories to payout details for categories with winners.
        :raises AssertionError: If the payout table does not have the expected structure.
        :raises ValueError: If categories are duplicated, missing, unsupported, or malformed.
        """
        rows = await self._get_validated_detail_rows()
        indexes = await self._get_details_column_indexes()
        details: dict[str, ResultDetails] = {}
        discovered_categories: set[BalotoHits] = set()

        for row in rows:
            category = await self._get_detail_category(row, indexes)

            if category in discovered_categories:
                error_message = f"Duplicate {self.game_name} hit category found in the result document: {category!r}."
                raise ValueError(error_message)

            discovered_categories.add(category)
            parsed_detail = await self._parse_detail_row(row, indexes)

            if parsed_detail is None:
                continue

            details[category] = parsed_detail

        if frozenset(discovered_categories) != self._EXPECTED_HITS:
            missing_categories = sorted(self._EXPECTED_HITS.difference(discovered_categories))
            error_message = (
                f"The {self.game_name} result document is missing expected hit categories: {missing_categories!r}."
            )
            raise ValueError(error_message)

        return details

    async def get_draw_title(self) -> str:
        """Return the complete draw title displayed by the result page."""
        return await get_required_text(self._game_id(self._page), "draw identifier")

    async def get_game_id(self) -> int:
        """
        Extract the displayed Baloto-style draw identifier.

        :return: Normalized integer draw identifier.
        :raises AssertionError: If the identifier locator does not resolve to one node.
        :raises ValueError: If the displayed identifier does not match the expected format.
        """
        text = await get_required_text(self._game_id(self._page), "draw identifier")
        match = self._GAME_ID_PATTERN.fullmatch(text)

        if match is None:
            error_message = f"Could not extract the {self.game_name} draw identifier from: {text!r}"
            raise ValueError(error_message)

        return es_localized_to_int(match.group(1))

    async def get_game_date(self) -> str:
        """Return the draw date exactly as displayed by the result page."""
        return await get_required_text(self._game_date(), "draw date")

    async def get_accumulated_prize(self) -> int:
        """
        Extract the accumulated prize in Colombian pesos.

        :return: Accumulated prize as an integer number of pesos.
        :raises AssertionError: If the prize locator does not resolve to one node.
        :raises ValueError: If the displayed prize does not match the expected format.
        """
        text = await get_required_text(self._accumulated_prize(), "accumulated prize")
        match = self._ACCUMULATED_PRIZE_PATTERN.fullmatch(text)

        if match is None:
            error_message = f"Could not extract the {self.game_name} accumulated prize from: {text!r}"
            raise ValueError(error_message)

        return parse_millions_to_pesos(match.group(1))

    async def get_balota(self) -> int:
        """
        Extract the red superball value from the result page.

        :return: Displayed superball as an integer.
        :raises TimeoutError: If Playwright cannot read the superball text.
        :raises ValueError: If the displayed value cannot be converted to an integer.
        """
        balota_text = await get_required_text(self._balota(), "balota")
        try:
            return int(balota_text)
        except ValueError as error:
            error_message = f"Invalid {self.game_name} superball value: {balota_text!r}"
            raise ValueError(error_message) from error

    async def get_detail(self, hits: str) -> ResultDetails | None:
        """
        Extract payout information for one Baloto-style hit category.

        :param hits: Supported hit category to retrieve.
        :return: Payout details, or ``None`` when the category has no winners.
        :raises AssertionError: If the payout table does not have the expected structure.
        :raises ValueError: If the category is unsupported, missing, duplicated, or malformed.
        """
        validated_hits = self._validate_hits(hits)
        rows = await self._get_validated_detail_rows()
        indexes = await self._get_details_column_indexes()
        matching_rows: list[Locator] = []

        for row in rows:
            category = await self._get_detail_category(row, indexes)

            if category == validated_hits:
                matching_rows.append(row)

        if not matching_rows:
            error_message = (
                f"The {self.game_name} result document does not contain the expected hit category {validated_hits!r}."
            )
            raise ValueError(error_message)

        if len(matching_rows) > 1:
            error_message = f"Duplicate {self.game_name} hit category found in the result document: {validated_hits!r}."
            raise ValueError(error_message)

        return await self._parse_detail_row(matching_rows[0], indexes)


class BalotoResultPage(BalotoRevanchaResultPage):
    """
    Represent and validate an individual Baloto draw result page.

    The page object reuses the shared Baloto/Revancha extraction implementation,
    configures the Baloto result URL, and registers validators for the Baloto page
    identity and expected draw identifier.
    """

    def __init__(self, page: Page, draw_id: int) -> None:
        """
        Initialize a Baloto page object for a specific draw.

        The constructor initializes the shared result-page state and registers the
        Baloto identity marker and draw-identifier validators.

        :param page: Playwright page used to navigate and extract the Baloto result.
        :param draw_id: Positive Baloto draw identifier expected in the loaded page.
        :raises ValueError: If ``draw_id`` is not greater than zero.
        :raises DuplicateValidatorError: If a validator name is already registered.
        """
        super().__init__(page, draw_id)
        self.validators.register(BalotoImageValidator(), DrawIdValidator(draw_id, self._game_id))

    @property
    def _result_url(self) -> HttpUrl:
        """Return the configured Baloto results URL."""
        return settings.baloto.result_url

    @property
    def game_name(self) -> str:
        """Return the canonical Baloto game name."""
        return "Baloto"


class RevanchaResultPage(BalotoRevanchaResultPage):
    """
    Represent and validate an individual Revancha draw result page.

    The page object reuses the shared Baloto/Revancha extraction implementation,
    configures the Revancha result URL, and registers validators for the Revancha
    page identity and expected draw identifier.
    """

    def __init__(self, page: Page, draw_id: int) -> None:
        """
        Initialize a Revancha page object for a specific draw.

        The constructor initializes the shared result-page state and registers the
        Revancha identity marker and draw-identifier validators.

        :param page: Playwright page used to navigate and extract the Revancha result.
        :param draw_id: Positive Revancha draw identifier expected in the loaded page.
        :raises ValueError: If ``draw_id`` is not greater than zero.
        :raises DuplicateValidatorError: If a validator name is already registered.
        """
        super().__init__(page, draw_id)
        self.validators.register(RevanchaImageValidator(), DrawIdValidator(draw_id, self._game_id))

    @property
    def _result_url(self) -> HttpUrl:
        """Return the configured Revancha results URL."""
        return settings.revancha.result_url

    @property
    def game_name(self) -> str:
        """Return the canonical Revancha game name."""
        return "Revancha"


def _normalize_baloto_hits_key(hits_text: str) -> str:
    """
    Normalize a displayed Baloto-style category to its canonical key.

    :param hits_text: Category text read from the payout table.
    :return: Canonical category key used by the extraction API.
    :raises ValueError: If the displayed category is unsupported.
    """
    normalized_hits = re.sub(r"\s+", "", hits_text).upper()

    category_mapping = {
        "0+SB": "SB",
        "1+SB": "SB",
        "SB": "SB",
        "2+SB": "2+SB",
        "3": "3",
        "3+SB": "3+SB",
        "4": "4",
        "4+SB": "4+SB",
        "5": "5",
        "5+SB": "5+SB",
    }

    category = category_mapping.get(normalized_hits)

    if category is None:
        error_message = f"Unsupported prize category: {hits_text!r}"
        raise ValueError(error_message)

    return category
