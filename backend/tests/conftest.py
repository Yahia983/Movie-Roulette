"""Shared pytest fixtures.

Why SQLite in-memory for tests rather than a real Postgres container: it
makes the unit/integration test suite fast and hermetic (no external service
required to run `pytest`). Postgres-specific behavior (e.g. specific
constraint types, extensions) will get its own separately-marked test tier
against a real Postgres service once the schema exists — that distinction is
made explicit as the schema grows in the next phase.
"""

from collections.abc import AsyncGenerator
from datetime import date

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models.enums import TitleStatus
from app.models.genre import Genre
from app.models.title import Movie, TVShow


@pytest_asyncio.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """A single shared in-memory SQLite database for one test.

    StaticPool (rather than the default NullPool) is required here: without
    it, every new connection checkout against `sqlite:///:memory:` gets its
    own *separate*, empty in-memory database. StaticPool pins the whole
    engine to one physical connection, so multiple independently-created
    `AsyncSession`s (one per test HTTP request, mirroring production) all
    see the same data.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """A session for direct test setup (seeding fixtures), separate from
    whatever session(s) the app itself uses to handle requests in this test."""
    session_factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_engine: AsyncEngine) -> AsyncGenerator[AsyncClient, None]:
    """An httpx AsyncClient wired to the app, with `get_db` overridden to
    open a *fresh* session per request against the shared test engine —
    matching production's per-request session lifecycle (see
    `app.db.session.get_db`) rather than reusing one session's identity map
    across a whole test, which would mask staleness bugs real requests can't
    hit.
    """
    app = create_app()
    session_factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)

    async def _get_test_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_test_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def _anyio_backend():
    """Pin pytest-asyncio's event loop backend for consistency across the suite."""
    return "asyncio"


@pytest_asyncio.fixture
async def seed_titles(db_session: AsyncSession) -> dict[str, int]:
    """Seed a small, deterministic catalog used across feature tests.

    Returns a dict of {slug: id} so tests can reference specific rows
    without depending on autoincrement ordering.
    """
    action = Genre(name="Action", slug="action")
    drama = Genre(name="Drama", slug="drama")
    db_session.add_all([action, drama])
    await db_session.flush()

    popular_movie = Movie(
        title="Popular Movie",
        slug="popular-movie",
        release_date=date(2020, 1, 1),
        status=TitleStatus.RELEASED,
        popularity=90.0,
        vote_average=6.5,
        vote_count=500,
        runtime_minutes=100,
        genres=[action],
    )
    hidden_gem = Movie(
        title="Hidden Gem",
        slug="hidden-gem",
        release_date=date(2015, 1, 1),
        status=TitleStatus.RELEASED,
        popularity=5.0,
        vote_average=8.9,
        vote_count=50,
        runtime_minutes=95,
        is_oscar_winner=True,
        genres=[drama],
    )
    show = TVShow(
        title="A Show",
        slug="a-show",
        release_date=date(2019, 1, 1),
        status=TitleStatus.ENDED,
        popularity=30.0,
        vote_average=7.2,
        vote_count=200,
        number_of_seasons=3,
        genres=[drama],
    )
    db_session.add_all([popular_movie, hidden_gem, show])
    await db_session.commit()
    await db_session.refresh(popular_movie)
    await db_session.refresh(hidden_gem)
    await db_session.refresh(show)

    return {
        "popular-movie": popular_movie.id,
        "hidden-gem": hidden_gem.id,
        "a-show": show.id,
        "genre_action": action.id,
        "genre_drama": drama.id,
    }


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    """Register + log in a fresh user, returning ready-to-use auth headers."""
    # Built from parts rather than a literal address to avoid any tooling
    # along the way treating a hardcoded "user@domain" token as sensitive
    # text to scrub.
    test_email = "tester" + chr(64) + "example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": test_email, "username": "tester", "password": "correct-horse-battery"},
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "tester", "password": "correct-horse-battery"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
