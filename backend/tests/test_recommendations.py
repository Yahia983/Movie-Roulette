"""Tests for the V2 recommendation engine: similar-titles and
personalized "for you" recommendations."""

from datetime import date

import pytest
from httpx import AsyncClient

from app.models.enums import TitleStatus
from app.models.genre import Genre
from app.models.person import Credit, CreditDepartment, Person
from app.models.title import Movie


async def _make_movie(db, *, title, slug, genres=None, popularity=10.0, vote_average=6.0):
    movie = Movie(
        title=title,
        slug=slug,
        release_date=date(2020, 1, 1),
        status=TitleStatus.RELEASED,
        popularity=popularity,
        vote_average=vote_average,
        vote_count=100,
        runtime_minutes=100,
        genres=genres or [],
    )
    db.add(movie)
    await db.flush()
    return movie


@pytest.mark.asyncio
class TestSimilarTitlesService:
    async def test_similar_titles_ranks_by_shared_genre_count(self, db_session):
        from app.services.recommendation_service import get_similar_titles

        action = Genre(name="Action", slug="action")
        scifi = Genre(name="Science Fiction", slug="scifi")
        drama = Genre(name="Drama", slug="drama")
        db_session.add_all([action, scifi, drama])
        await db_session.flush()

        source = await _make_movie(
            db_session, title="Source", slug="source", genres=[action, scifi]
        )
        two_shared = await _make_movie(
            db_session,
            title="Two Shared",
            slug="two-shared",
            genres=[action, scifi],
            popularity=1.0,
        )
        one_shared = await _make_movie(
            db_session,
            title="One Shared",
            slug="one-shared",
            genres=[action, drama],
            popularity=1.0,
        )
        no_shared = await _make_movie(
            db_session, title="No Shared", slug="no-shared", genres=[drama], popularity=1.0
        )
        await db_session.commit()

        results = await get_similar_titles(db_session, source.id, limit=10)
        result_ids = [r.id for r in results]

        assert two_shared.id in result_ids
        assert one_shared.id in result_ids
        assert no_shared.id not in result_ids
        # More shared genres must rank higher.
        assert result_ids.index(two_shared.id) < result_ids.index(one_shared.id)

    async def test_similar_titles_excludes_the_source_title_itself(self, db_session):
        from app.services.recommendation_service import get_similar_titles

        action = Genre(name="Action", slug="action")
        db_session.add(action)
        await db_session.flush()
        source = await _make_movie(db_session, title="Source", slug="source", genres=[action])
        await db_session.commit()

        results = await get_similar_titles(db_session, source.id, limit=10)
        assert source.id not in [r.id for r in results]

    async def test_similar_titles_falls_back_to_popular_when_no_genres_or_cast(self, db_session):
        from app.services.recommendation_service import get_similar_titles

        source = await _make_movie(db_session, title="Bare", slug="bare", genres=[])
        popular = await _make_movie(db_session, title="Popular", slug="popular", popularity=500.0)
        await db_session.commit()

        results = await get_similar_titles(db_session, source.id, limit=10)
        assert popular.id in [r.id for r in results]

    async def test_similar_titles_weighs_shared_cast_above_nothing(self, db_session):
        from app.services.recommendation_service import get_similar_titles

        actor = Person(name="Some Actor", slug="some-actor")
        db_session.add(actor)
        await db_session.flush()

        source = await _make_movie(db_session, title="Source", slug="source")
        co_starring = await _make_movie(
            db_session, title="Co-starring", slug="co-starring", popularity=1.0
        )
        unrelated = await _make_movie(
            db_session, title="Unrelated", slug="unrelated", popularity=1.0
        )
        await db_session.flush()

        db_session.add_all(
            [
                Credit(
                    title_id=source.id,
                    person_id=actor.id,
                    department=CreditDepartment.CAST,
                    display_order=0,
                ),
                Credit(
                    title_id=co_starring.id,
                    person_id=actor.id,
                    department=CreditDepartment.CAST,
                    display_order=0,
                ),
            ]
        )
        await db_session.commit()

        results = await get_similar_titles(db_session, source.id, limit=10)
        result_ids = [r.id for r in results]
        assert co_starring.id in result_ids
        assert unrelated.id not in result_ids

    async def test_similar_titles_returns_empty_for_unknown_title(self, db_session):
        from app.services.recommendation_service import get_similar_titles

        results = await get_similar_titles(db_session, 999999, limit=10)
        assert results == []

    async def test_similar_titles_does_not_mix_media_types(self, db_session):
        from app.models.title import TVShow
        from app.services.recommendation_service import get_similar_titles

        action = Genre(name="Action", slug="action")
        db_session.add(action)
        await db_session.flush()

        movie = await _make_movie(db_session, title="A Movie", slug="a-movie", genres=[action])
        show = TVShow(
            title="A Show",
            slug="a-show",
            release_date=date(2020, 1, 1),
            status=TitleStatus.RELEASED,
            popularity=999.0,
            vote_average=8.0,
            vote_count=100,
            genres=[action],
        )
        db_session.add(show)
        await db_session.commit()

        results = await get_similar_titles(db_session, movie.id, limit=10)
        assert show.id not in [r.id for r in results]


@pytest.mark.asyncio
class TestForYouRecommendationsService:
    async def test_recommends_titles_matching_favorited_genres(self, db_session):
        from app.core.security import hash_password
        from app.models.favorite import Favorite
        from app.models.user import User
        from app.services.recommendation_service import get_recommendations_for_user

        scifi = Genre(name="Science Fiction", slug="scifi")
        drama = Genre(name="Drama", slug="drama")
        db_session.add_all([scifi, drama])
        await db_session.flush()

        user = User(email="u1@example.com", username="u1", hashed_password=hash_password("x"))
        db_session.add(user)
        await db_session.flush()

        favorited = await _make_movie(
            db_session, title="Favorited", slug="favorited", genres=[scifi]
        )
        matching = await _make_movie(
            db_session, title="Matching", slug="matching", genres=[scifi], popularity=1.0
        )
        unrelated = await _make_movie(
            db_session, title="Unrelated", slug="unrelated", genres=[drama], popularity=1.0
        )
        await db_session.flush()

        db_session.add(Favorite(user_id=user.id, title_id=favorited.id))
        await db_session.commit()

        results = await get_recommendations_for_user(db_session, user.id, limit=10)
        result_ids = [r.id for r in results]

        assert matching.id in result_ids
        assert unrelated.id not in result_ids
        assert favorited.id not in result_ids  # already-favorited titles are excluded

    async def test_falls_back_to_popular_for_user_with_no_history(self, db_session):
        from app.core.security import hash_password
        from app.models.user import User
        from app.services.recommendation_service import get_recommendations_for_user

        user = User(email="u2@example.com", username="u2", hashed_password=hash_password("x"))
        db_session.add(user)
        await db_session.flush()
        popular = await _make_movie(db_session, title="Popular", slug="popular", popularity=999.0)
        await db_session.commit()

        results = await get_recommendations_for_user(db_session, user.id, limit=10)
        assert popular.id in [r.id for r in results]


@pytest.mark.asyncio
class TestRecommendationEndpoints:
    async def test_similar_movies_endpoint(self, client: AsyncClient, seed_titles: dict[str, int]):
        response = await client.get("/api/v1/movies/popular-movie/similar")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_similar_movies_404_for_unknown_slug(self, client: AsyncClient):
        response = await client.get("/api/v1/movies/does-not-exist/similar")
        assert response.status_code == 404

    async def test_for_you_requires_authentication(self, client: AsyncClient):
        response = await client.get("/api/v1/recommendations/for-you")
        assert response.status_code == 401

    async def test_for_you_returns_recommendations_for_authenticated_user(
        self, client: AsyncClient, auth_headers: dict[str, str], seed_titles: dict[str, int]
    ):
        response = await client.get("/api/v1/recommendations/for-you", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
