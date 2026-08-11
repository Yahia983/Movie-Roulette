"""Redis connection management and a minimal cache helper.

Why this is wired up now, before any feature needs it: trending/popular
lists, search results, and roulette session state are all natural caching
candidates later. Establishing one shared connection pool and a tiny
get/set/delete wrapper here means later services depend on this module
instead of each opening their own Redis client with inconsistent settings.
"""

import json
from typing import Any

from redis.asyncio import ConnectionPool, Redis

from app.core.config import get_settings

settings = get_settings()

# A shared pool avoids the overhead of establishing a new connection per
# request; asyncio-redis pools are safe to share across coroutines.
_pool = ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)


def get_redis() -> Redis:
    """Return a Redis client backed by the shared connection pool.

    A new lightweight client object is returned per call (cheap — it does not
    open a new socket), but all clients share the same underlying pool.
    """
    return Redis(connection_pool=_pool)


async def cache_get_json(key: str) -> Any | None:
    """Fetch and JSON-decode a cached value, or None on miss/absence."""
    redis = get_redis()
    raw = await redis.get(key)
    return json.loads(raw) if raw is not None else None


async def cache_set_json(key: str, value: Any, ttl_seconds: int | None = None) -> None:
    """JSON-encode and store a value with an expiry (defaults to config TTL)."""
    redis = get_redis()
    ttl = ttl_seconds if ttl_seconds is not None else settings.CACHE_DEFAULT_TTL_SECONDS
    await redis.set(key, json.dumps(value), ex=ttl)


async def cache_delete(key: str) -> None:
    """Invalidate a cached value."""
    redis = get_redis()
    await redis.delete(key)
