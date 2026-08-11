"""Async database engine and session management.

Why async: the roulette engine and recommendation services will eventually
need to fan out to multiple I/O-bound lookups (DB + Redis + future vector
search) per request. An async stack lets a single worker handle many
concurrent requests during that I/O wait instead of blocking a whole thread
per request, which is the difference between needing 4 workers and needing 40
at the same load.
"""

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

# pool_pre_ping guards against stale connections (e.g. after a DB restart or
# a cloud provider's idle-connection reaper) causing hard-to-debug errors on
# the first query of a new request.
#
# pool_size/max_overflow are Postgres-pool-specific and unsupported by
# SQLite's NullPool (used for local dev/tests) — only passed for non-SQLite
# URLs so the same code path works against both without branching elsewhere.
_engine_kwargs: dict[str, Any] = {"echo": settings.DB_ECHO, "pool_pre_ping": True}
if not settings.DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
    _engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a request-scoped async DB session.

    The session is always closed at the end of the request via the
    context manager, and any uncommitted work is rolled back on error so a
    failed request never leaves a half-applied transaction hanging around.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
