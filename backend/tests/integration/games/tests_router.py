"""Integration tests for the write routes in ``app.games.router``."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.games import repository

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_post_without_admin_key_returns_401_and_does_not_persist(
    client: AsyncClient,
    db_session: AsyncSession,
    miloto_draw_payload: dict[str, object],
) -> None:
    """POSTing without ``X-Admin-Api-Key`` is rejected and never reaches the database."""
    draw_id = miloto_draw_payload["game_id"]

    response = await client.post(f"/miloto/draw/{draw_id}", json=miloto_draw_payload)

    assert response.status_code == 401

    stored = await repository.get_draw(db_session, "miloto", draw_id)
    assert stored is None
