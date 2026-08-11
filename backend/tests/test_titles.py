"""Movie/TV browse, filter, search, and detail-page tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_browse_movies_returns_only_movies(
    client: AsyncClient, seed_titles: dict[str, int]
) -> None:
    response = await client.get("/api/v1/movies")
    assert response.status_code == 200
    body = response.json()
    slugs = {item["slug"] for item in body["items"]}
    assert slugs == {"popular-movie", "hidden-gem"}
    assert body["total"] == 2


@pytest.mark.asyncio
async def test_browse_tv_shows_returns_only_shows(
    client: AsyncClient, seed_titles: dict[str, int]
) -> None:
    response = await client.get("/api/v1/tv-shows")
    assert response.status_code == 200
    body = response.json()
    assert [item["slug"] for item in body["items"]] == ["a-show"]


@pytest.mark.asyncio
async def test_browse_sorts_by_popularity_by_default(
    client: AsyncClient, seed_titles: dict[str, int]
) -> None:
    response = await client.get("/api/v1/movies")
    titles = [item["title"] for item in response.json()["items"]]
    assert titles == ["Popular Movie", "Hidden Gem"]


@pytest.mark.asyncio
async def test_browse_filters_by_min_rating(
    client: AsyncClient, seed_titles: dict[str, int]
) -> None:
    response = await client.get("/api/v1/movies", params={"min_rating": 8.0})
    body = response.json()
    assert [item["slug"] for item in body["items"]] == ["hidden-gem"]


@pytest.mark.asyncio
async def test_browse_filters_by_genre(client: AsyncClient, seed_titles: dict[str, int]) -> None:
    response = await client.get("/api/v1/movies", params={"genre_ids": seed_titles["genre_action"]})
    body = response.json()
    assert [item["slug"] for item in body["items"]] == ["popular-movie"]


@pytest.mark.asyncio
async def test_browse_search_matches_title_substring(
    client: AsyncClient, seed_titles: dict[str, int]
) -> None:
    response = await client.get("/api/v1/movies", params={"search": "hidden"})
    body = response.json()
    assert [item["slug"] for item in body["items"]] == ["hidden-gem"]


@pytest.mark.asyncio
async def test_movie_detail_returns_full_shape(
    client: AsyncClient, seed_titles: dict[str, int]
) -> None:
    response = await client.get("/api/v1/movies/popular-movie")
    assert response.status_code == 200
    body = response.json()
    assert body["runtime_minutes"] == 100
    assert body["media_type"] == "movie"
    assert body["genres"][0]["name"] == "Action"


@pytest.mark.asyncio
async def test_tv_show_detail_returns_full_shape(
    client: AsyncClient, seed_titles: dict[str, int]
) -> None:
    response = await client.get("/api/v1/tv-shows/a-show")
    assert response.status_code == 200
    body = response.json()
    assert body["number_of_seasons"] == 3
    assert body["media_type"] == "tv_show"


@pytest.mark.asyncio
async def test_movie_detail_404_for_unknown_slug(
    client: AsyncClient, seed_titles: dict[str, int]
) -> None:
    response = await client.get("/api/v1/movies/does-not-exist")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_movie_slug_never_resolves_as_tv_show(
    client: AsyncClient, seed_titles: dict[str, int]
) -> None:
    """A TV show's slug must 404 under /movies — media types are isolated."""
    response = await client.get("/api/v1/movies/a-show")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_genres(client: AsyncClient, seed_titles: dict[str, int]) -> None:
    response = await client.get("/api/v1/genres")
    assert response.status_code == 200
    names = {g["name"] for g in response.json()}
    assert names == {"Action", "Drama"}
