"""Favorites, watch-later, and ratings tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_add_and_list_favorite(
    client: AsyncClient, seed_titles: dict[str, int], auth_headers: dict[str, str]
) -> None:
    title_id = seed_titles["popular-movie"]

    add_response = await client.put(f"/api/v1/favorites/{title_id}", headers=auth_headers)
    assert add_response.status_code == 204

    list_response = await client.get("/api/v1/favorites", headers=auth_headers)
    body = list_response.json()
    assert body["total"] == 1
    assert body["items"][0]["title"]["slug"] == "popular-movie"


@pytest.mark.asyncio
async def test_favoriting_twice_is_idempotent(
    client: AsyncClient, seed_titles: dict[str, int], auth_headers: dict[str, str]
) -> None:
    title_id = seed_titles["popular-movie"]
    await client.put(f"/api/v1/favorites/{title_id}", headers=auth_headers)
    await client.put(f"/api/v1/favorites/{title_id}", headers=auth_headers)

    list_response = await client.get("/api/v1/favorites", headers=auth_headers)
    assert list_response.json()["total"] == 1


@pytest.mark.asyncio
async def test_remove_favorite(
    client: AsyncClient, seed_titles: dict[str, int], auth_headers: dict[str, str]
) -> None:
    title_id = seed_titles["popular-movie"]
    await client.put(f"/api/v1/favorites/{title_id}", headers=auth_headers)

    remove_response = await client.delete(f"/api/v1/favorites/{title_id}", headers=auth_headers)
    assert remove_response.status_code == 204

    list_response = await client.get("/api/v1/favorites", headers=auth_headers)
    assert list_response.json()["total"] == 0


@pytest.mark.asyncio
async def test_favorite_nonexistent_title_404s(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.put("/api/v1/favorites/99999", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_favorites_require_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/favorites")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_watch_later_add_list_remove(
    client: AsyncClient, seed_titles: dict[str, int], auth_headers: dict[str, str]
) -> None:
    title_id = seed_titles["a-show"]

    await client.put(f"/api/v1/watch-later/{title_id}", headers=auth_headers)
    list_response = await client.get("/api/v1/watch-later", headers=auth_headers)
    assert list_response.json()["total"] == 1

    await client.delete(f"/api/v1/watch-later/{title_id}", headers=auth_headers)
    list_response = await client.get("/api/v1/watch-later", headers=auth_headers)
    assert list_response.json()["total"] == 0


@pytest.mark.asyncio
async def test_rate_title_creates_rating(
    client: AsyncClient, seed_titles: dict[str, int], auth_headers: dict[str, str]
) -> None:
    title_id = seed_titles["popular-movie"]
    response = await client.put(
        f"/api/v1/ratings/{title_id}",
        json={"score": 8, "review_text": "Solid."},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["score"] == 8


@pytest.mark.asyncio
async def test_rate_title_upserts_on_second_call(
    client: AsyncClient, seed_titles: dict[str, int], auth_headers: dict[str, str]
) -> None:
    title_id = seed_titles["popular-movie"]
    await client.put(f"/api/v1/ratings/{title_id}", json={"score": 5}, headers=auth_headers)
    second = await client.put(
        f"/api/v1/ratings/{title_id}", json={"score": 9}, headers=auth_headers
    )
    assert second.json()["score"] == 9


@pytest.mark.asyncio
async def test_rate_title_rejects_out_of_range_score(
    client: AsyncClient, seed_titles: dict[str, int], auth_headers: dict[str, str]
) -> None:
    title_id = seed_titles["popular-movie"]
    response = await client.put(
        f"/api/v1/ratings/{title_id}", json={"score": 15}, headers=auth_headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_viewing_a_movie_records_history(
    client: AsyncClient, seed_titles: dict[str, int], auth_headers: dict[str, str]
) -> None:
    await client.get("/api/v1/movies/popular-movie", headers=auth_headers)
    response = await client.get("/api/v1/history", headers=auth_headers)
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["title"]["slug"] == "popular-movie"
