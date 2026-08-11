"""Fixtures for the Postgres integration test tier.

Why this tier exists separately from the main SQLite-backed suite: SQLite
does not enforce foreign key constraints by default (no `PRAGMA
foreign_keys=ON` is set anywhere in this codebase), so cascade-delete
behavior, NOT NULL violations at the DB level, and real constraint
enforcement are all effectively *untested* by the fast suite even though
they appear to pass. This tier runs the actual Alembic migrations against a
real PostgreSQL database and exercises exactly that class of behavior.

Skipped automatically (not failed) when no Postgres test database is
reachable, so the main `pytest` run in an environment without Postgres
installed doesn't need special configuration to stay green. CI runs it as
its own job against a real `postgres:` service container.
"""

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Overridable via env var so CI can point at its own service container
# without editing code; defaults to the local dev Postgres instance.
POSTGRES_TEST_URL = os.environ.get(
    "POSTGRES_TEST_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/movieroulette_test",
)


def _run_migrations() -> None:
    """Run Alembic migrations against the Postgres test DB synchronously.

    Alembic's migration runner is sync-only (see alembic/env.py), so this
    shells out to the sync driver rather than trying to run migrations
    through the async engine used everywhere else in the app.

    Setting `sqlalchemy.url` on the `Config` object alone is NOT enough:
    `alembic/env.py` unconditionally overwrites it from
    `app.core.config.get_settings().DATABASE_URL_SYNC` (by design, so a
    normal `alembic upgrade head` always targets whatever the app itself is
    configured for). Since `get_settings()` is `@lru_cache`d and very likely
    already been called earlier in this test process (importing anything
    under `app.*` triggers it), we have to override the env var *and* clear
    the cache so `env.py`'s call to `get_settings()` picks up the Postgres
    test URL instead of whatever `.env` says.
    """
    from app.core.config import get_settings

    sync_url = POSTGRES_TEST_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    original_env_value = os.environ.get("DATABASE_URL_SYNC")
    os.environ["DATABASE_URL_SYNC"] = sync_url
    get_settings.cache_clear()

    try:
        from alembic import command
        from alembic.config import Config

        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        alembic_cfg = Config(os.path.join(backend_dir, "alembic.ini"))
        alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
        alembic_cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
        command.downgrade(alembic_cfg, "base")
        command.upgrade(alembic_cfg, "head")
    finally:
        # Restore so the rest of the test process (and any subsequent
        # fixture use) still sees the app's normal configured database.
        if original_env_value is None:
            os.environ.pop("DATABASE_URL_SYNC", None)
        else:
            os.environ["DATABASE_URL_SYNC"] = original_env_value
        get_settings.cache_clear()


@pytest_asyncio.fixture
async def pg_session() -> AsyncGenerator[AsyncSession, None]:
    """A session against a real, freshly-migrated Postgres database.

    Skips (doesn't fail) the test if Postgres isn't reachable — this tier
    is explicitly opt-in for local development (it requires a running
    Postgres instance) and mandatory only in its own CI job.
    """
    engine = create_async_engine(POSTGRES_TEST_URL)
    try:
        async with engine.connect():
            pass
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"Postgres test database not reachable: {exc}")

    await engine.dispose()

    _run_migrations()

    engine = create_async_engine(POSTGRES_TEST_URL)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()
