"""A thin async client for The Movie Database (TMDB) API v3.

Why this is a separate module from the ingestion service: this module knows
*how to talk to TMDB* (auth, endpoints, pagination, rate-limit backoff) and
nothing about *what to do with the response* (upserting rows, resolving
genre IDs). That split is what makes `ingestion_service.py` unit-testable
against plain dicts shaped like TMDB responses, with zero network calls and
zero dependency on this client actually working.

This client is exercised by integration tests only when `TMDB_API_KEY` is
configured; the ingestion pipeline itself is fully tested without it (see
`tests/test_ingestion_service.py`).
"""

import asyncio
import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.themoviedb.org/3"
_MAX_RETRIES = 3
_RETRY_BACKOFF_SECONDS = 2.0


class TMDBError(Exception):
    """Raised for any TMDB API failure (auth, not-found, rate-limited-out)."""


class TMDBNotConfiguredError(TMDBError):
    """Raised when no TMDB_API_KEY is set. Callers (the sync CLI) should
    catch this and exit with a clear message rather than a stack trace."""


class TMDBClient:
    """Async TMDB API client. One instance per sync run; close it when done."""

    def __init__(self, api_key: str | None = None, http_client: httpx.AsyncClient | None = None):
        settings = get_settings()
        self._api_key = api_key or settings.TMDB_API_KEY
        # Accepting an injected httpx.AsyncClient (rather than always
        # constructing our own) is what lets tests substitute an
        # httpx.MockTransport-backed client with zero real network calls.
        self._client = http_client or httpx.AsyncClient(base_url=_BASE_URL, timeout=15.0)
        self._owns_client = http_client is None

    async def __aenter__(self) -> "TMDBClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self._api_key:
            raise TMDBNotConfiguredError(
                "TMDB_API_KEY is not set. Configure it in .env to run a catalog sync."
            )

        request_params = {"api_key": self._api_key, **(params or {})}

        last_error: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = await self._client.get(path, params=request_params)
            except httpx.RequestError as exc:
                last_error = exc
                logger.warning(
                    "TMDB request error on attempt %d/%d: %s", attempt, _MAX_RETRIES, exc
                )
            else:
                if response.status_code == 429:
                    # TMDB rate limiting: back off and retry rather than
                    # failing the whole sync over a transient throttle.
                    retry_after = float(response.headers.get("Retry-After", _RETRY_BACKOFF_SECONDS))
                    logger.info("TMDB rate limited; retrying in %.1fs", retry_after)
                    await asyncio.sleep(retry_after)
                    continue
                if response.status_code == 404:
                    raise TMDBError(f"TMDB resource not found: {path}")
                if response.status_code >= 400:
                    raise TMDBError(
                        f"TMDB request to {path} failed with "
                        f"{response.status_code}: {response.text}"
                    )
                return dict(response.json())

            await asyncio.sleep(_RETRY_BACKOFF_SECONDS * attempt)

        raise TMDBError(
            f"TMDB request to {path} failed after {_MAX_RETRIES} attempts"
        ) from last_error

    async def get_genre_list(self, media_type: str) -> list[dict[str, Any]]:
        """media_type: 'movie' or 'tv'."""
        data = await self._get(f"/genre/{media_type}/list")
        return list(data.get("genres", []))

    async def get_popular(self, media_type: str, page: int = 1) -> dict[str, Any]:
        """media_type: 'movie' or 'tv'. Returns the raw paginated response."""
        return await self._get(f"/{media_type}/popular", {"page": page})

    async def get_details(self, media_type: str, tmdb_id: int) -> dict[str, Any]:
        """Full details for one title, with credits appended in one call via
        TMDB's `append_to_response` — avoids a second round-trip per title."""
        return await self._get(
            f"/{media_type}/{tmdb_id}", {"append_to_response": "credits,watch/providers"}
        )
