"""Tests for the ingestion service, using realistic TMDB-shaped fixtures.

No network access involved anywhere in this file — that's the whole point
of splitting ingestion logic from the TMDB HTTP client (see
ingestion_service.py's module docstring).
"""

from datetime import date

import pytest
from sqlalchemy import select

from app.models.enums import CreditDepartment, MediaType, TitleStatus
from app.models.person import Credit
from app.models.streaming import TitleAvailability
from app.models.title import Movie, TVShow
from app.services import ingestion_service


def _movie_fixture(**overrides) -> dict:
    """A TMDB /movie/{id} response shape, with append_to_response=credits,watch/providers."""
    base = {
        "id": 603,
        "title": "The Matrix",
        "overview": "A computer hacker learns the truth about reality.",
        "tagline": "Welcome to the Real World.",
        "poster_path": "/matrix-poster.jpg",
        "backdrop_path": "/matrix-backdrop.jpg",
        "release_date": "1999-03-30",
        "original_language": "en",
        "status": "Released",
        "popularity": 82.3,
        "vote_average": 8.2,
        "vote_count": 24000,
        "runtime": 136,
        "budget": 63000000,
        "revenue": 465000000,
        "genres": [{"id": 28, "name": "Action"}, {"id": 878, "name": "Science Fiction"}],
        "credits": {
            "cast": [
                {
                    "id": 6384,
                    "name": "Keanu Reeves",
                    "character": "Neo",
                    "order": 0,
                    "profile_path": "/keanu.jpg",
                },
                {
                    "id": 2,
                    "name": "Laurence Fishburne",
                    "character": "Morpheus",
                    "order": 1,
                    "profile_path": None,
                },
            ],
            "crew": [
                {
                    "id": 9339,
                    "name": "Lana Wachowski",
                    "job": "Director",
                    "department": "Directing",
                    "profile_path": None,
                },
                {
                    "id": 9340,
                    "name": "Lilly Wachowski",
                    "job": "Writer",
                    "department": "Writing",
                    "profile_path": None,
                },
                {
                    "id": 9999,
                    "name": "Some Gaffer",
                    "job": "Gaffer",
                    "department": "Camera",
                    "profile_path": None,
                },
            ],
        },
        "watch/providers": {
            "results": {
                "US": {
                    "link": "https://www.themoviedb.org/movie/603-the-matrix/watch",
                    "flatrate": [
                        {"provider_id": 8, "provider_name": "Netflix", "logo_path": "/netflix.jpg"}
                    ],
                }
            }
        },
    }
    base.update(overrides)
    return base


class TestParsing:
    def test_parse_status_known_movie_status(self):
        assert ingestion_service.parse_status(MediaType.MOVIE, "Released") == TitleStatus.RELEASED
        assert ingestion_service.parse_status(MediaType.MOVIE, "Canceled") == TitleStatus.CANCELED

    def test_parse_status_known_tv_status(self):
        assert ingestion_service.parse_status(MediaType.TV_SHOW, "Ended") == TitleStatus.ENDED
        assert (
            ingestion_service.parse_status(MediaType.TV_SHOW, "Returning Series")
            == TitleStatus.IN_PRODUCTION
        )

    def test_parse_status_unknown_defaults_to_released(self):
        assert (
            ingestion_service.parse_status(MediaType.MOVIE, "Some New Status")
            == TitleStatus.RELEASED
        )
        assert ingestion_service.parse_status(MediaType.MOVIE, None) == TitleStatus.RELEASED

    def test_parse_date_valid(self):
        assert ingestion_service.parse_date("1999-03-30") == date(1999, 3, 30)

    def test_parse_date_empty_string_is_none(self):
        assert ingestion_service.parse_date("") is None

    def test_parse_date_none_is_none(self):
        assert ingestion_service.parse_date(None) is None

    def test_parse_date_malformed_is_none_not_an_error(self):
        assert ingestion_service.parse_date("not-a-date") is None


@pytest.mark.asyncio
class TestUpsertTitle:
    async def test_creates_new_movie_with_all_fields(self, db_session):
        movie = await ingestion_service.upsert_title(db_session, MediaType.MOVIE, _movie_fixture())

        assert isinstance(movie, Movie)
        assert movie.tmdb_id == 603
        assert movie.title == "The Matrix"
        assert movie.slug == "the-matrix-1999"
        assert movie.runtime_minutes == 136
        assert movie.budget == 63000000
        assert movie.status == TitleStatus.RELEASED
        assert movie.release_date == date(1999, 3, 30)

    async def test_attaches_genres(self, db_session):
        movie = await ingestion_service.upsert_title(db_session, MediaType.MOVIE, _movie_fixture())
        genre_names = {g.name for g in movie.genres}
        assert genre_names == {"Action", "Science Fiction"}

    async def test_attaches_cast_and_filtered_crew(self, db_session):
        movie = await ingestion_service.upsert_title(db_session, MediaType.MOVIE, _movie_fixture())

        credits = (
            (await db_session.execute(select(Credit).where(Credit.title_id == movie.id)))
            .scalars()
            .all()
        )

        cast_credits = [c for c in credits if c.department == CreditDepartment.CAST]
        director_credits = [c for c in credits if c.department == CreditDepartment.DIRECTOR]
        writer_credits = [c for c in credits if c.department == CreditDepartment.WRITER]

        assert len(cast_credits) == 2
        assert {c.character_name for c in cast_credits} == {"Neo", "Morpheus"}
        assert len(director_credits) == 1
        assert len(writer_credits) == 1
        # The "Gaffer" crew job isn't in our tracked department list — it
        # must not produce a Credit row at all.
        assert len(credits) == 4

    async def test_attaches_streaming_availability(self, db_session):
        movie = await ingestion_service.upsert_title(db_session, MediaType.MOVIE, _movie_fixture())

        availability = (
            (
                await db_session.execute(
                    select(TitleAvailability).where(TitleAvailability.title_id == movie.id)
                )
            )
            .scalars()
            .all()
        )

        assert len(availability) == 1
        assert availability[0].region == "US"

    async def test_upsert_is_idempotent_on_tmdb_id(self, db_session):
        first = await ingestion_service.upsert_title(db_session, MediaType.MOVIE, _movie_fixture())
        second = await ingestion_service.upsert_title(
            db_session, MediaType.MOVIE, _movie_fixture(popularity=99.9)
        )

        assert first.id == second.id
        assert second.popularity == 99.9

        all_matrix_rows = (
            (await db_session.execute(select(Movie).where(Movie.tmdb_id == 603))).scalars().all()
        )
        assert len(all_matrix_rows) == 1

    async def test_resyncing_replaces_credits_rather_than_duplicating(self, db_session):
        await ingestion_service.upsert_title(db_session, MediaType.MOVIE, _movie_fixture())
        await ingestion_service.upsert_title(db_session, MediaType.MOVIE, _movie_fixture())

        movie = (await db_session.execute(select(Movie).where(Movie.tmdb_id == 603))).scalar_one()
        credits = (
            (await db_session.execute(select(Credit).where(Credit.title_id == movie.id)))
            .scalars()
            .all()
        )
        assert len(credits) == 4  # not 8 — re-sync must not double credits

    async def test_two_titles_same_name_and_year_get_distinct_slugs(self, db_session):
        first = await ingestion_service.upsert_title(
            db_session,
            MediaType.MOVIE,
            _movie_fixture(id=1, title="Dune", release_date="2021-10-22"),
        )
        second = await ingestion_service.upsert_title(
            db_session,
            MediaType.MOVIE,
            _movie_fixture(id=2, title="Dune", release_date="2021-10-22"),
        )
        assert first.slug != second.slug
        assert first.slug == "dune-2021"
        assert second.slug == "dune-2021-2"

    async def test_creates_tv_show_with_tv_specific_fields(self, db_session):
        tv_fixture = {
            "id": 1399,
            "name": "Game of Thrones",
            "overview": "Nine noble families fight for control.",
            "first_air_date": "2011-04-17",
            "last_air_date": "2019-05-19",
            "status": "Ended",
            "popularity": 300.0,
            "vote_average": 8.4,
            "vote_count": 21000,
            "number_of_seasons": 8,
            "number_of_episodes": 73,
            "in_production": False,
            "episode_run_time": [60],
            "genres": [{"id": 18, "name": "Drama"}],
            "credits": {"cast": [], "crew": []},
        }
        show = await ingestion_service.upsert_title(db_session, MediaType.TV_SHOW, tv_fixture)

        assert isinstance(show, TVShow)
        assert show.number_of_seasons == 8
        assert show.in_production is False
        assert show.episode_runtime_minutes == 60
        assert show.slug == "game-of-thrones-2011"

    async def test_missing_overview_becomes_none_not_empty_string(self, db_session):
        movie = await ingestion_service.upsert_title(
            db_session, MediaType.MOVIE, _movie_fixture(overview="")
        )
        assert movie.overview is None
