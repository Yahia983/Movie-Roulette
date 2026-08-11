"""Roulette engine tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_spin_with_no_filters_returns_a_result(
    client: AsyncClient, seed_titles: dict[str, int]
) -> None:
    response = await client.post("/api/v1/roulette/spin", json={"filters": {}})
    assert response.status_code == 200
    body = response.json()
    assert body["result"] is not None
    assert body["candidate_count"] == 3  # all seeded titles


@pytest.mark.asyncio
async def test_spin_respects_media_type_filter(
    client: AsyncClient, seed_titles: dict[str, int]
) -> None:
    response = await client.post(
        "/api/v1/roulette/spin", json={"filters": {"media_type": "tv_show"}}
    )
    body = response.json()
    assert body["result"]["media_type"] == "tv_show"
    assert body["candidate_count"] == 1


@pytest.mark.asyncio
async def test_spin_hidden_gems_only_matches_low_popularity_high_rating(
    client: AsyncClient, seed_titles: dict[str, int]
) -> None:
    response = await client.post("/api/v1/roulette/spin", json={"filters": {"hidden_gems": True}})
    body = response.json()
    assert body["result"]["slug"] == "hidden-gem"


@pytest.mark.asyncio
async def test_spin_oscar_winners_only(client: AsyncClient, seed_titles: dict[str, int]) -> None:
    response = await client.post("/api/v1/roulette/spin", json={"filters": {"oscar_winners": True}})
    body = response.json()
    assert body["result"]["slug"] == "hidden-gem"


@pytest.mark.asyncio
async def test_spin_with_impossible_filters_returns_null_result(
    client: AsyncClient, seed_titles: dict[str, int]
) -> None:
    response = await client.post("/api/v1/roulette/spin", json={"filters": {"min_rating": 9.9}})
    assert response.status_code == 200
    assert response.json()["result"] is None


@pytest.mark.asyncio
async def test_spin_works_anonymously(client: AsyncClient, seed_titles: dict[str, int]) -> None:
    """The roulette engine must not require authentication — per spec, it's
    a no-signup-wall feature."""
    response = await client.post("/api/v1/roulette/spin", json={"filters": {}})
    assert response.status_code == 200
