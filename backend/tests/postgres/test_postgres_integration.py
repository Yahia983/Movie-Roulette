"""Tests that specifically require real Postgres semantics — foreign key
cascade enforcement, unique constraint violations, and the actual Alembic
migration chain — none of which SQLite's default configuration enforces or
fully exercises. See conftest.py's module docstring for the full rationale.
"""

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.enums import TitleStatus
from app.models.favorite import Favorite
from app.models.genre import Genre
from app.models.title import Movie, Title
from app.models.user import User

pytestmark = pytest.mark.postgres


@pytest.mark.asyncio
async def test_migrations_run_cleanly_against_postgres(pg_session):
    """The mere fact this fixture resolved means `alembic upgrade head`
    succeeded end-to-end against real Postgres — this test's body just
    confirms the resulting schema is queryable."""
    result = await pg_session.execute(select(Genre))
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_deleting_a_title_cascades_to_its_movie_subtype_row(pg_session):
    """Joined-table inheritance relies on titles.id -> movies.title_id
    being ON DELETE CASCADE — SQLite would silently leave an orphaned
    `movies` row behind without foreign_keys=ON; Postgres enforces this by
    default, which is exactly what this test needs to actually verify."""
    movie = Movie(
        title="Cascade Test",
        slug="cascade-test",
        release_date=date(2020, 1, 1),
        status=TitleStatus.RELEASED,
        popularity=1.0,
        vote_average=5.0,
        vote_count=1,
    )
    pg_session.add(movie)
    await pg_session.commit()
    movie_id = movie.id

    title_row = await pg_session.get(Title, movie_id)
    await pg_session.delete(title_row)
    await pg_session.commit()

    remaining = await pg_session.get(Movie, movie_id)
    assert remaining is None


@pytest.mark.asyncio
async def test_deleting_a_title_cascades_to_favorites(pg_session):
    """A user's favorite referencing a deleted title must itself be
    deleted (ON DELETE CASCADE on favorites.title_id), not left dangling
    or raise a foreign key violation."""
    from app.core.security import hash_password

    user = User(
        email="cascade@example.com", username="cascadeuser", hashed_password=hash_password("x")
    )
    movie = Movie(
        title="Cascade Favorite",
        slug="cascade-favorite",
        release_date=date(2020, 1, 1),
        status=TitleStatus.RELEASED,
        popularity=1.0,
        vote_average=5.0,
        vote_count=1,
    )
    pg_session.add_all([user, movie])
    await pg_session.commit()

    pg_session.add(Favorite(user_id=user.id, title_id=movie.id))
    await pg_session.commit()

    title_row = await pg_session.get(Title, movie.id)
    await pg_session.delete(title_row)
    await pg_session.commit()

    remaining_favorites = (
        (await pg_session.execute(select(Favorite).where(Favorite.user_id == user.id)))
        .scalars()
        .all()
    )
    assert remaining_favorites == []


@pytest.mark.asyncio
async def test_duplicate_email_violates_unique_constraint(pg_session):
    """Confirms the DB-level unique constraint is real and enforced —
    the service layer's pre-check (auth_service.register_user) is a UX
    nicety, not the actual guarantee; this test verifies the guarantee."""
    from app.core.security import hash_password

    pg_session.add(
        User(email="dup@example.com", username="dup1", hashed_password=hash_password("x"))
    )
    await pg_session.commit()

    pg_session.add(
        User(email="dup@example.com", username="dup2", hashed_password=hash_password("x"))
    )
    with pytest.raises(IntegrityError):
        await pg_session.commit()


@pytest.mark.asyncio
async def test_rating_score_check_constraint_enforced_at_db_level(pg_session):
    """The `score BETWEEN 1 AND 10` check constraint on ratings must reject
    out-of-range values even if application code has a bug that skips
    Pydantic validation — this is the actual safety net, not the API schema."""
    from app.core.security import hash_password
    from app.models.rating import Rating

    user = User(email="rater@example.com", username="rater", hashed_password=hash_password("x"))
    movie = Movie(
        title="Rating Constraint Test",
        slug="rating-constraint-test",
        release_date=date(2020, 1, 1),
        status=TitleStatus.RELEASED,
        popularity=1.0,
        vote_average=5.0,
        vote_count=1,
    )
    pg_session.add_all([user, movie])
    await pg_session.commit()

    pg_session.add(Rating(user_id=user.id, title_id=movie.id, score=99))
    with pytest.raises(IntegrityError):
        await pg_session.commit()
