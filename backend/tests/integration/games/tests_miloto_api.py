"""
Integration tests for the Miloto draw API.

Exercises the ``/miloto/draw/{draw_id}`` routes against a real Postgres
starting with authentication and persistence behavior for the write routes.
"""

import datetime
from typing import TYPE_CHECKING, Any, cast

import pytest_asyncio
from app.core.config import settings
from app.core.database import async_session_factory
from app.games.repository import get_draw
from app.shared.date_utils import full_date
from fastapi import status

from tests.integration.games.conftest import RESERVED_TEST_GAME_ID

if TYPE_CHECKING:
    import httpx
    from app.games.schemas import GameSchema, MilotoSchema


async def test_post_without_admin_key_returns_401_and_persists_nothing(http_client: httpx.AsyncClient) -> None:
    """
    A write without the ``X-Admin-Api-Key`` header is rejected with 401 and the draw is not stored.

    The POST route depends on ``require_admin_api_key``, so FastAPI short-circuits
    with an unauthorized response before the endpoint (and its DB insert) runs;
    the follow-up public GET then confirms no row was persisted.
    """
    payload: dict[str, str | int | list[int] | None] = {
        "game": "miloto",
        "game_id": RESERVED_TEST_GAME_ID,
        "game_date": "2024-01-15",
        "numbers": [1, 2, 3, 4, 5],
        "accumulated": 120_000_000,
    }

    post_response = await http_client.post(f"/miloto/draw/{RESERVED_TEST_GAME_ID}", json=payload)
    assert post_response.status_code == status.HTTP_401_UNAUTHORIZED
    assert post_response.json()["detail"] == "Invalid or missing admin API key."

    get_response = await http_client.get(f"/miloto/draw/{RESERVED_TEST_GAME_ID}")
    assert get_response.status_code == status.HTTP_404_NOT_FOUND


async def test_post_with_admin_key_persists_draw(
    http_client: httpx.AsyncClient, miloto_payload: dict[str, Any]
) -> None:
    """
    A POST with the admin key stores a draw under the reserved test id.

    The request body is built in code with ``game_id`` set to the reserved test
    id so the path and body always agree. The 200 response echoes the stored
    draw; the row is then fetched back out of the ``miloto_draws`` table to
    confirm it was really persisted (not just acknowledged).

    """
    payload: dict[str, Any] = miloto_payload
    admin_api_key = settings.admin_api_key.get_secret_value()
    headers = {"X-Admin-Api-Key": admin_api_key}

    post_response = await http_client.post(f"/miloto/draw/{RESERVED_TEST_GAME_ID}", json=payload, headers=headers)
    assert post_response.status_code == status.HTTP_200_OK, post_response.text

    get_response = await http_client.get(f"/miloto/draw/{RESERVED_TEST_GAME_ID}")
    assert get_response.status_code == status.HTTP_200_OK
    assert get_response.json()["game_id"] == RESERVED_TEST_GAME_ID
    assert get_response.json()["numbers"] == [4, 18, 26, 31, 39]

    stored = await _fetch_miloto_draw(RESERVED_TEST_GAME_ID)
    assert stored is not None
    miloto_stored: MilotoSchema = cast("MilotoSchema", stored)
    assert miloto_stored.game_id == RESERVED_TEST_GAME_ID
    assert miloto_stored.numbers == payload["numbers"]
    assert miloto_stored.accumulated == payload["accumulated"]
    assert miloto_stored.hits_5 is None
    assert miloto_stored.hits_4 is not None
    assert miloto_stored.hits_4.prize_for_winner == payload["hits_4"]["prize_for_winner"]
    assert miloto_stored.hits_4.winners == payload["hits_4"]["winners"]
    assert miloto_stored.hits_3 is not None
    assert miloto_stored.hits_3.prize_for_winner == payload["hits_3"]["prize_for_winner"]
    assert miloto_stored.hits_3.winners == payload["hits_3"]["winners"]
    assert miloto_stored.hits_2 is not None
    assert miloto_stored.hits_2.prize_for_winner == payload["hits_2"]["prize_for_winner"]
    assert miloto_stored.hits_2.winners == payload["hits_2"]["winners"]
    assert miloto_stored.game_date == datetime.date(2024, 2, 5)


async def test_post_already_existing_id(http_client: httpx.AsyncClient, miloto_payload: dict[str, Any]) -> None:
    """
    Posting the same reserved game_id twice is rejected with 409 Conflict.

    The first insert succeeds and the second attempt must not overwrite it.
    """
    admin_api_key = settings.admin_api_key.get_secret_value()
    headers = {"X-Admin-Api-Key": admin_api_key}
    post_response = await http_client.post(
        f"/miloto/draw/{RESERVED_TEST_GAME_ID}", json=miloto_payload, headers=headers
    )
    assert post_response.status_code == status.HTTP_200_OK, post_response.text

    get_response = await http_client.get(f"/miloto/draw/{RESERVED_TEST_GAME_ID}")
    assert get_response.status_code == status.HTTP_200_OK
    assert get_response.json()["game_id"] == RESERVED_TEST_GAME_ID

    # inserting the same game_id again should return 409 Conflict
    post_response_2 = await http_client.post(
        f"/miloto/draw/{RESERVED_TEST_GAME_ID}", json=miloto_payload, headers=headers
    )
    assert post_response_2.status_code == status.HTTP_409_CONFLICT
    json_response = post_response_2.json()
    assert json_response["detail"].startswith(f"Draw {RESERVED_TEST_GAME_ID} already exists")


async def test_post_already_existing_date(http_client: httpx.AsyncClient, miloto_payload: dict[str, Any]) -> None:
    """
    A payload whose game_date is already taken returns 409 Conflict.

    The game_date is unique per game, so a colliding date is rejected.
    """
    payload: dict[str, Any] = miloto_payload.copy()
    payload["game_date"] = "2023-10-23"  # using existing date
    admin_api_key = settings.admin_api_key.get_secret_value()

    headers = {"X-Admin-Api-Key": admin_api_key}
    post_response = await http_client.post(f"/miloto/draw/{RESERVED_TEST_GAME_ID}", json=payload, headers=headers)
    assert post_response.status_code == status.HTTP_409_CONFLICT, post_response.text
    json_response = post_response.json()
    assert "date collides with another miloto draw" in json_response["detail"], json_response["detail"]


async def test_get_non_existing_draw_returns_404(http_client: httpx.AsyncClient) -> None:
    """
    A GET for a non-existing draw id returns 404.

    The reserved test id is cleared before each test, so this path is guaranteed
    to be unpopulated at the start of the test.
    """
    get_response = await http_client.get(f"/miloto/draw/{RESERVED_TEST_GAME_ID}")
    assert get_response.status_code == status.HTTP_404_NOT_FOUND
    assert get_response.json()["detail"] == f"No miloto game id {RESERVED_TEST_GAME_ID} is stored."


async def test_get_validate_draw(http_client: httpx.AsyncClient) -> None:
    """
    Validate the persisted first miloto draw.

    Fetches the configured first draw and checks its stored game_id and game_date.
    """
    get_response = await http_client.get(f"/miloto/draw/{settings.miloto.first_id}")
    assert get_response.status_code == status.HTTP_200_OK, get_response.text

    stored = await _fetch_miloto_draw(settings.miloto.first_id)
    assert stored is not None
    miloto_stored: MilotoSchema = cast("MilotoSchema", stored)
    assert miloto_stored.game_id == settings.miloto.first_id
    assert miloto_stored.game_date == settings.miloto.first_date


async def test_delete_draw(http_client: httpx.AsyncClient, miloto_payload: dict[str, Any]) -> None:
    """
    A DELETE for a draw id returns 200 and the draw is removed.

    The reserved test id is cleared before each test, so this path is guaranteed
    to be unpopulated at the start of the test.
    """
    admin_api_key = settings.admin_api_key.get_secret_value()
    headers = {"X-Admin-Api-Key": admin_api_key}

    post_response = await http_client.post(
        f"/miloto/draw/{RESERVED_TEST_GAME_ID}", json=miloto_payload, headers=headers
    )
    assert post_response.status_code == status.HTTP_200_OK

    # Now delete the draw
    delete_response = await http_client.delete(f"/miloto/draw/{RESERVED_TEST_GAME_ID}", headers=headers)
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    # Verify that the draw has been deleted
    get_response = await http_client.get(f"/miloto/draw/{RESERVED_TEST_GAME_ID}")
    assert get_response.status_code == status.HTTP_404_NOT_FOUND


async def test_patch_with_admin_key_updates_draw(
    http_client: httpx.AsyncClient, miloto_payload: dict[str, Any]
) -> None:
    """
    A PATCH with the admin key replaces the stored draw body under the reserved id.

    The reserved id is POSTed first so the draw exists; PATCHing with an updated
    ``miloto_payload`` (different numbers and accumulated prize) then overwrites
    the stored row. The public GET and a direct table read both confirm the new
    values replaced the old ones.

    """
    admin_api_key = settings.admin_api_key.get_secret_value()
    headers = {"X-Admin-Api-Key": admin_api_key}

    post_response = await http_client.post(
        f"/miloto/draw/{RESERVED_TEST_GAME_ID}", json=miloto_payload, headers=headers
    )
    assert post_response.status_code == status.HTTP_200_OK, post_response.text
    assert post_response.json()["numbers"] == [4, 18, 26, 31, 39]

    updated_payload: dict[str, Any] = {
        **miloto_payload,
        "numbers": [7, 11, 22, 30, 38],
        "accumulated": 200_000_000,
    }

    patch_response = await http_client.patch(
        f"/miloto/draw/{RESERVED_TEST_GAME_ID}", json=updated_payload, headers=headers
    )
    assert patch_response.status_code == status.HTTP_200_OK, patch_response.text
    assert patch_response.json()["accumulated"] == 200_000_000

    get_response = await http_client.get(f"/miloto/draw/{RESERVED_TEST_GAME_ID}")
    assert get_response.status_code == status.HTTP_200_OK, get_response.text
    assert get_response.json()["numbers"] == [7, 11, 22, 30, 38]
    assert get_response.json()["accumulated"] == 200_000_000

    stored = await _fetch_miloto_draw(RESERVED_TEST_GAME_ID)
    assert stored is not None
    miloto_stored: MilotoSchema = cast("MilotoSchema", stored)
    assert miloto_stored.numbers == [7, 11, 22, 30, 38]
    assert miloto_stored.accumulated == 200_000_000
    assert miloto_stored.game_date == datetime.date(2024, 2, 5)


async def test_patch_non_existing_draw_returns_404(
    http_client: httpx.AsyncClient, miloto_payload: dict[str, Any]
) -> None:
    """
    A PATCH for a draw that is not stored returns 404.

    The reserved id is cleared before each test, so PATCHing it reaches
    ``_replace_draw``'s not-found branch and returns 404 instead of inserting.

    """
    admin_api_key = settings.admin_api_key.get_secret_value()
    headers = {"X-Admin-Api-Key": admin_api_key}

    patch_response = await http_client.patch(
        f"/miloto/draw/{RESERVED_TEST_GAME_ID}", json=miloto_payload, headers=headers
    )
    assert patch_response.status_code == status.HTTP_404_NOT_FOUND, patch_response.text
    assert patch_response.json()["detail"] == f"No miloto with id {RESERVED_TEST_GAME_ID} is stored."


@pytest_asyncio.fixture
async def paginated_draw_ids(
    http_client: httpx.AsyncClient,
) -> list[int]:
    """
    Create a spread of Miloto draws with monotonically increasing reserved ids.

    The ids are chosen well above any pre-existing draw (the ``first_id``
    configured in ``settings.miloto``) so that, with ``game_id`` descending
    order, the created draws always lead the list regardless of how the
    database was seeded. Each id is cleaned up by ``remove_test_created_rows``.

    :param http_client: The ASGI-bound httpx client.
    :return: The list of created ``game_id`` values, in ascending creation order.
    """
    await _post_miloto(
        http_client=http_client, game_id=100_000_011, game_date="2024-03-11", numbers=[1, 2, 3, 4, 5], hits_5=None
    )
    await _post_miloto(
        http_client=http_client, game_id=100_000_012, game_date="2024-03-12", numbers=[6, 7, 8, 9, 10], hits_5=None
    )
    await _post_miloto(
        http_client=http_client, game_id=100_000_013, game_date="2024-03-13", numbers=[11, 12, 13, 14, 15], hits_5=None
    )
    await _post_miloto(
        http_client=http_client, game_id=100_000_014, game_date="2024-03-14", numbers=[16, 17, 18, 19, 20], hits_5=None
    )
    await _post_miloto(
        http_client=http_client, game_id=100_000_015, game_date="2024-03-15", numbers=[21, 22, 23, 24, 25], hits_5=None
    )
    return [100_000_011, 100_000_012, 100_000_013, 100_000_014, 100_000_015]


async def test_list_draws_returns_paginated_envelope(
    http_client: httpx.AsyncClient, paginated_draw_ids: list[int]
) -> None:
    """
    ``GET /miloto/draws`` returns a paginated envelope listing stored draws.

    The response exposes the ``items``/``page``/``size``/``total``/``pages``
    fields, defaults to page 1 / size 20, and returns the created draws first,
    ordered by ``game_id`` descending. ``total`` and ``pages`` are computed
    from the whole table (which may hold pre-existing draws), so they are
    asserted for internal consistency rather than absolute values.
    """
    response = await http_client.get("/miloto/draws")
    assert response.status_code == status.HTTP_200_OK, response.text

    body = response.json()
    assert set(body) == {"items", "page", "size", "total", "pages"}
    assert body["page"] == 1
    assert body["size"] == 20

    items = body["items"]
    assert len(items) <= body["size"]
    assert body["total"] >= len(paginated_draw_ids)
    assert body["pages"] == (body["total"] + body["size"] - 1) // body["size"]

    first_item = items[0]
    assert first_item["game_id"] == paginated_draw_ids[-1]
    assert first_item["game_date"] == full_date(datetime.date(2024, 3, 15))
    assert first_item["numbers"] == [21, 22, 23, 24, 25]
    assert first_item["accumulated"] == "$150M"
    assert first_item["jackpot"] is False

    item_ids = [item["game_id"] for item in items]
    assert item_ids[: len(paginated_draw_ids)] == list(reversed(paginated_draw_ids))


async def test_list_draws_respects_size_across_pages(
    http_client: httpx.AsyncClient, paginated_draw_ids: list[int]
) -> None:
    """
    ``GET /miloto/draws`` slices results by ``size`` and advances by ``page``.

    With ``size=2`` the created draws (the five highest ids) span three pages:
    page 1 holds the two newest, page 2 the next two, and page 3 the last one,
    with no overlap between consecutive pages.
    """
    page_one = await http_client.get("/miloto/draws", params={"page": 1, "size": 2})
    assert page_one.status_code == status.HTTP_200_OK, page_one.text
    page_one_ids = [item["game_id"] for item in page_one.json()["items"]]
    assert page_one_ids == [100_000_015, 100_000_014]

    page_two = await http_client.get("/miloto/draws", params={"page": 2, "size": 2})
    assert page_two.status_code == status.HTTP_200_OK, page_two.text
    page_two_ids = [item["game_id"] for item in page_two.json()["items"]]
    assert page_two_ids == [100_000_013, 100_000_012]

    page_three = await http_client.get("/miloto/draws", params={"page": 3, "size": 2})
    assert page_three.status_code == status.HTTP_200_OK, page_three.text
    page_three_ids = [item["game_id"] for item in page_three.json()["items"]]
    assert page_three_ids[0] == 100_000_011

    assert set(page_one_ids).isdisjoint(page_two_ids)
    assert set(page_two_ids).isdisjoint(page_three_ids)


async def test_list_draws_rejects_out_of_range_params(http_client: httpx.AsyncClient) -> None:
    """
    ``GET /miloto/draws`` rejects out-of-range pagination query parameters.

    ``page`` must be >= 1 and ``size`` must be within 1..20; a ``page`` of 0,
    a ``size`` of 0, and a ``size`` above 20 all yield a 422 validation error.
    """
    for params in ({"page": 0}, {"size": 0}, {"size": 21}):
        response = await http_client.get("/miloto/draws", params=params)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT, params


async def _post_miloto(
    http_client: httpx.AsyncClient,
    game_id: int,
    game_date: str,
    numbers: list[int],
    hits_5: dict[str, int] | None,
) -> None:
    """
    POST a Miloto draw under the given id and assert it was stored.

    :param http_client: The ASGI-bound httpx client.
    :param game_id: The draw's official number.
    :param game_date: The draw date, as an ISO date string.
    :param numbers: The drawn numbers.
    :param hits_5: Optional ``hits_5`` payout tier, controlling the ``jackpot`` flag.
    :return: None.
    """
    admin_api_key = settings.admin_api_key.get_secret_value()
    headers = {"X-Admin-Api-Key": admin_api_key}
    payload: dict[str, Any] = {
        "game": "miloto",
        "game_id": game_id,
        "game_date": game_date,
        "numbers": numbers,
        "accumulated": 150_000_000,
        "hits_2": {"prize_for_winner": 4_000, "winners": 4_000},
        "hits_3": {"prize_for_winner": 45_000, "winners": 400},
        "hits_4": {"prize_for_winner": 800_000, "winners": 10},
        "hits_5": hits_5,
    }
    response = await http_client.post(f"/miloto/draw/{game_id}", json=payload, headers=headers)
    assert response.status_code == status.HTTP_200_OK, response.text


async def _fetch_miloto_draw(game_id: int) -> GameSchema | None:
    """Return the persisted ``miloto_draws`` row for the given game_id, or ``None``."""
    async with async_session_factory() as session:
        return await get_draw(session, game="miloto", draw_id=game_id)
