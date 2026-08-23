"""
Provide asynchronous extraction and validation for MiLoto draw results.

The module defines ``MilotoPage``, which navigates through the shared base-page
lifecycle and extracts the draw identifier, date, winning numbers, accumulated
prize, and payout details from MiLoto result documents. MiLoto-specific page
identity is verified through its draw identifier, metadata, and page title.

The implementation keeps MiLoto selectors and category rules independent from
the shared Baloto/Revancha result structure.
"""

import re
from typing import TYPE_CHECKING, ClassVar, Literal, get_args

from pydantic import TypeAdapter

from app.config.app_settings import settings
from app.schemas.base import ResultDetailsSchema
from app.utils.number_utils import es_localized_to_int, parse_millions_to_pesos
from app.utils.playwright_utils.base_page import (
    BasePage,
    extract_detail_integer,
    get_inner_text,
    get_required_text,
    require_exact_count,
)
from app.utils.playwright_utils.validators import DrawIdValidator, MetaContentValidator, PageTitleValidator

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page
    from pydantic import HttpUrl


type MilotoHits = Literal["2", "3", "4", "5"]

_MILOTO_HITS_ADAPTER: TypeAdapter[MilotoHits] = TypeAdapter(MilotoHits)


def _validate_hits(hits: str) -> MilotoHits:
    normalized_hits = re.sub(r"\s+", "", hits).upper()
    return _MILOTO_HITS_ADAPTER.validate_python(normalized_hits)


class MilotoPage(BasePage):
    """
    Represent, validate, and extract an individual MiLoto draw result.

    The page object defines MiLoto-specific locators, result patterns, prize-card
    parsing, and supported hit categories. During initialization it extends the
    base URL validation with draw-identifier, metadata, and page-title validators.
    """

    _DETAILS_COUNT = 4

    # region Pattern Members

    _GAME_ID_PATTERN = re.compile(r"^SORTEO\s+#(\d{1,3}(?:\.\d{3})*)$", re.IGNORECASE)

    _GAME_DATE_PATTERN = re.compile(
        r"^\d{1,2}\s+de\s+[A-Za-zÁÉÍÓÚáéíóúÑñ]+\s+de\s+\d{4}$",
        re.IGNORECASE,
    )
    
    _ACCUMULATED_PRIZE_PATTERN = re.compile(
        r"^\s*ACUMULADO DEL SORTEO:\s*\$([\d.]+)\s+MILLONES\s*$",
        re.IGNORECASE,
    )

    _EXPECTED_HITS: ClassVar[frozenset[MilotoHits]] = frozenset(get_args(MilotoHits.__value__))

    # endregion

    def __init__(self, page: Page, draw_id: int) -> None:
        """
        Initialize a MiLoto page object for a specific draw.

        The constructor initializes the common result-page state and registers the
        MiLoto draw-identifier, metadata-content, and page-title validators.

        :param page: Playwright page used to navigate and extract the MiLoto result.
        :param draw_id: Positive MiLoto draw identifier expected in the loaded page.
        :raises ValueError: If ``draw_id`` is not greater than zero.
        :raises DuplicateValidatorError: If a validator name is already registered.
        """
        super().__init__(page, draw_id)

        self.validators.register(
            DrawIdValidator(draw_id, self._game_id),
            MetaContentValidator(),
            PageTitleValidator(),
        )

    # region Locators

    async def _get_validated_detail_cards(self) -> list[Locator]:
        """
        Return the complete validated collection of MiLoto payout cards.

        :return: Four locators representing the supported MiLoto hit categories.
        :raises AssertionError: If the result document does not contain exactly four cards.
        """
        cards_locator = self._detail_cards()
        await require_exact_count(cards_locator, self._DETAILS_COUNT, "prize-category cards")
        return await cards_locator.all()

    @classmethod
    def _game_id(cls, page: Page) -> Locator:
        """
        Build the locator for the MiLoto draw identifier.

        :param page: Playwright page containing the MiLoto result document.
        :return: Locator matching the displayed MiLoto draw identifier.
        """
        return page.get_by_text(
            cls._GAME_ID_PATTERN,
        ).describe("Miloto draw identifier")

    def _game_date(self) -> Locator:
        """Return the locator containing the displayed Miloto draw date."""
        return self._page.get_by_text(self._GAME_DATE_PATTERN).describe("Draw date")

    def _winner_numbers(self) -> Locator:
        """Return the locator containing the five Miloto winning numbers."""
        result_container = (
            self._page.locator(
                "div.text-center.mt-5.mb-5",
            )
            .filter(
                has_text=re.compile(
                    r"ACUMULADO DEL SORTEO",
                    re.IGNORECASE,
                ),
            )
            .describe("container ACUMULADO DEL SORTEO")
        )

        return result_container.locator(".yellow-ball").describe("winner number")

    def _accumulated_prize(self) -> Locator:
        """Return the locator containing the Miloto accumulated prize."""
        return self._page.get_by_text(
            self._ACCUMULATED_PRIZE_PATTERN,
        ).describe("ACUMULADO DEL SORTEO")

    def _detail_cards(self) -> Locator:
        """Return the locator containing all Miloto payout cards."""
        return (
            self._page.locator(
                "div.mt-4.bg-white.rounded",
            )
            .filter(
                has=self._page.locator(".aciertos"),
            )
            .describe("Class aciertos")
        )

    def _card_payout_section(self, card: Locator) -> Locator:
        """
        Return the payout section contained in a MiLoto detail card.

        :param card: MiLoto detail-card locator.
        :return: Locator containing the card's prize-per-winner information.
        """
        return (
            card.locator(
                "div.light-blue",
            )
            .filter(
                has_text=re.compile(
                    r"Premio por ganador",
                    re.IGNORECASE,
                ),
            )
            .describe("Premio por ganador")
        )

    def _ps_highlighted_values(self, payout_section: Locator) -> Locator:
        """
        Return the highlighted payout values from a card section.

        :param payout_section: Locator containing a MiLoto card's payout information.
        :return: Locator matching the highlighted prize and winner-count values.
        """
        return payout_section.locator("span.pink-light").describe("Payout section")

    def _card_category(self, card: Locator) -> Locator:
        """
        Return the hit-category locator contained in a MiLoto detail card.

        :param card: MiLoto detail-card locator.
        :return: Locator containing the card's hit category.
        """
        return card.locator(".fs-aciertos").describe("Aciertos")

    # endregion

    # region Protected service methods and properties

    @property
    def _result_url(self) -> HttpUrl:
        """Return the configured MiLoto results URL."""
        return settings.baloto_settings.miloto_baseurl

    async def _get_detail_category(self, card: Locator) -> MilotoHits:
        """
        Extract and validate the hit category from a MiLoto detail card.

        :param card: MiLoto detail-card locator.
        :return: Validated MiLoto hit category.
        :raises AssertionError: If the category locator does not resolve to one node.
        :raises ValueError: If the document contains an unsupported hit category.
        """
        category_text = await get_required_text(self._card_category(card), "detail category")
        return _validate_hits(category_text)

    async def _parse_detail_card(self, card: Locator, category: MilotoHits) -> ResultDetailsSchema | None:
        """
        Parse payout information from one validated MiLoto detail card.

        :param card: MiLoto detail-card locator to parse.
        :param category: Validated hit category associated with the card.
        :return: Payout details, or ``None`` when the category has no winners.
        :raises AssertionError: If required payout nodes do not have the expected count.
        :raises ValueError: If a displayed winner count or prize cannot be parsed.
        """
        payout_section = self._card_payout_section(card)
        await require_exact_count(payout_section, 1, category)

        highlighted_values = self._ps_highlighted_values(payout_section)
        await require_exact_count(highlighted_values, 2, category)

        prize_text = await get_inner_text(highlighted_values.nth(0))
        winners_text = await get_inner_text(highlighted_values.nth(1))
        winners = extract_detail_integer(
            winners_text,
            "winner count",
            self.game_name,
        )

        if winners == 0:
            return None

        prize_for_winner = extract_detail_integer(
            prize_text,
            "prize per winner",
            self.game_name,
        )

        return ResultDetailsSchema(
            prize_for_winner=prize_for_winner,
            winners=winners,
        )

    # endregion

    # region Public Methods and Properties

    @property
    def game_name(self) -> str:
        """Return the canonical MiLoto game name."""
        return "Miloto"

    async def get_game_id(self) -> int:
        """
        Extract the MiLoto draw identifier displayed by the result page.

        :return: Normalized integer draw identifier.
        :raises AssertionError: If the identifier locator does not resolve to one node.
        :raises ValueError: If the displayed identifier does not match the MiLoto format.
        """
        game_id = self._game_id(self._page)
        text = await get_required_text(game_id, "draw")
        match = self._GAME_ID_PATTERN.fullmatch(text)

        if match is None:
            error_message = f"Could not extract the MiLoto game identifier from: {text!r}"
            raise ValueError(error_message)

        return es_localized_to_int(match.group(1))

    async def get_game_date(self) -> str:
        """
        Extract the MiLoto draw date exactly as displayed.

        :return: Displayed draw date in Spanish.
        :raises AssertionError: If the draw-date locator does not resolve to one node.
        """
        game_date = self._game_date()
        return await get_required_text(game_date, "draw date")

    async def get_accumulated_prize(self) -> int:
        """
        Extract the MiLoto accumulated prize in Colombian pesos.

        :return: Accumulated prize as an integer number of pesos.
        :raises AssertionError: If the prize locator does not resolve to one node.
        :raises ValueError: If the displayed prize does not match the expected format.
        """
        accumulated_prize = self._accumulated_prize()
        text = await get_required_text(accumulated_prize, "accumulated prize")
        match = self._ACCUMULATED_PRIZE_PATTERN.fullmatch(text)

        if match is None:
            error_message = f"Could not extract the MiLoto accumulated prize from: {text!r}"
            raise ValueError(error_message)

        return parse_millions_to_pesos(match.group(1))

    async def get_detail(self, hits: str) -> ResultDetailsSchema | None:
        """
        Extract payout information for one MiLoto hit category.

        :param hits: Supported MiLoto hit category to retrieve.
        :return: Payout details, or ``None`` when the category has no winners.
        :raises ValueError: If ``hits`` is unsupported or a payout value cannot be parsed.
        :raises AssertionError: If the category does not resolve to exactly one card.
        """
        validated_hits = _MILOTO_HITS_ADAPTER.validate_python(hits)
        category_pattern = re.compile(
            rf"^\s*{re.escape(validated_hits)}\s*$",
        )

        matching_cards = self._detail_cards().filter(
            has=self._page.locator(".fs-aciertos").filter(
                has_text=category_pattern,
            ),
        )

        await require_exact_count(matching_cards, 1, str(validated_hits))
        return await self._parse_detail_card(matching_cards.first, validated_hits)

    async def get_details(self) -> dict[str, ResultDetailsSchema]:
        """
        Extract payout information for every MiLoto hit category.

        Categories with no winners are validated but omitted from the returned mapping.

        :return: Mapping of hit categories to payout details for categories with winners.
        :raises AssertionError: If the expected card or payout structure is not present.
        :raises ValueError: If categories are duplicated, missing, unsupported, or malformed.
        """
        cards = await self._get_validated_detail_cards()
        details: dict[str, ResultDetailsSchema] = {}
        discovered_categories: set[MilotoHits] = set()

        for card in cards:
            category = await self._get_detail_category(card)

            if category in discovered_categories:
                error_message = f"Duplicate MiLoto hit category found in the result document: {category!r}."
                raise ValueError(error_message)

            discovered_categories.add(category)
            parsed_detail = await self._parse_detail_card(card, category)

            if parsed_detail is None:
                continue

            details[category] = parsed_detail

        if frozenset(discovered_categories) != self._EXPECTED_HITS:
            missing_categories = sorted(self._EXPECTED_HITS.difference(discovered_categories))
            error_message = f"The MiLoto result document is missing expected hit categories: {missing_categories!r}."
            raise ValueError(error_message)

        return details

    # endregion


# async def assert_draw_id(self, draw_id: int) -> None:
#     """
#     Assert the loaded page displays the given draw identifier.

#     The expected value is formatted with Spanish thousands separators and
#     compared against the draw-identifier node using a Playwright assertion.

#     :param draw_id: Draw identifier expected in the loaded result document.
#     :raises AssertionError: If the displayed identifier does not match.
#     """
#     localized_draw_id = int_to_localized_es(draw_id)
#     expected_text = re.compile(
#         rf"^SORTEO\s+#{re.escape(localized_draw_id)}$",
#         re.IGNORECASE,
#     )

#     await expect(
#         self._game_id(self._page),
#         f"Loaded page should display draw {draw_id}",
#     ).to_have_text(expected_text)
 

