"""Tests for the TMDB HTTP client, using httpx.MockTransport — no real
network access, but exercising the actual request/response handling code
(retries, error mapping, rate-limit backoff) rather than mocking it away."""

import httpx
import pytest

from app.services.tmdb_client import TMDBClient, TMDBError, TMDBNotConfiguredError


@pytest.mark.asyncio
async def test_raises_when_no_api_key_configured():
    client = TMDBClient(
        api_key=None, http_client=httpx.AsyncClient(base_url="https://api.themoviedb.org/3")
    )
    with pytest.raises(TMDBNotConfiguredError):
        await client.get_genre_list("movie")
    await client.close()


@pytest.mark.asyncio
async def test_successful_request_returns_json():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["api_key"] == "test-key"
        return httpx.Response(200, json={"genres": [{"id": 28, "name": "Action"}]})

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(base_url="https://api.themoviedb.org/3", transport=transport)
    client = TMDBClient(api_key="test-key", http_client=http_client)

    genres = await client.get_genre_list("movie")
    assert genres == [{"id": 28, "name": "Action"}]
    await client.close()


@pytest.mark.asyncio
async def test_404_raises_tmdb_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"status_message": "not found"})

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(base_url="https://api.themoviedb.org/3", transport=transport)
    client = TMDBClient(api_key="test-key", http_client=http_client)

    with pytest.raises(TMDBError):
        await client.get_details("movie", 999999999)
    await client.close()


@pytest.mark.asyncio
async def test_rate_limit_retries_then_succeeds():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"genres": []})

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(base_url="https://api.themoviedb.org/3", transport=transport)
    client = TMDBClient(api_key="test-key", http_client=http_client)

    genres = await client.get_genre_list("tv")
    assert genres == []
    assert call_count["n"] == 2
    await client.close()


@pytest.mark.asyncio
async def test_get_details_requests_credits_and_providers_in_one_call():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["append_to_response"] = request.url.params["append_to_response"]
        return httpx.Response(200, json={"id": 603, "title": "The Matrix"})

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(base_url="https://api.themoviedb.org/3", transport=transport)
    client = TMDBClient(api_key="test-key", http_client=http_client)

    data = await client.get_details("movie", 603)
    assert data["id"] == 603
    assert captured["append_to_response"] == "credits,watch/providers"
    await client.close()
