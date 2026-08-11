"""The Title hierarchy: the polymorphic base for everything a user can
browse, favorite, rate, or have the roulette engine select.

Design note: this uses SQLAlchemy joined-table inheritance. Every field
common to movies and TV shows (name, artwork, synopsis, popularity, ratings)
lives on `Title`; only genuinely type-specific fields live on `Movie` /
`TVShow`. Every other feature in the app — favorites, collections, ratings,
search, the roulette engine — queries/references `Title` and never needs to
know or care whether a given row is a movie or a show.
"""

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Column, Date, ForeignKey, Index, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import MediaType, TitleStatus

if TYPE_CHECKING:
    from app.models.genre import Genre
    from app.models.person import Credit
    from app.models.streaming import TitleAvailability

# Many-to-many association between titles and genres. A plain Table (not a
# mapped class) is sufficient since the relationship itself carries no extra
# data beyond the two foreign keys.
title_genres = Table(
    "title_genres",
    Base.metadata,
    Column("title_id", ForeignKey("titles.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True),
)


class Title(TimestampMixin, Base):
    """Base table for any piece of watchable media (movie or TV show).

    Every browsable/favoritable/ratable entity in the app is a `Title` row.
    Subclasses (`Movie`, `TVShow`) add only their type-specific columns via
    joined-table inheritance, keyed on `media_type`.
    """

    __tablename__ = "titles"
    __table_args__ = (
        # The roulette engine and browse/filter pages constantly filter by
        # media_type + genre + popularity/rating together, so a composite
        # index on the highest-cardinality common filter combination pays
        # for itself immediately; single-column indexes below cover the rest.
        Index("ix_titles_media_type_popularity", "media_type", "popularity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Discriminator column driving SQLAlchemy's polymorphic loading.
    media_type: Mapped[MediaType] = mapped_column(String(20), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # URL-safe unique identifier used in routes (e.g. /movies/the-matrix-1999)
    # instead of exposing raw sequential IDs in URLs.
    slug: Mapped[str] = mapped_column(String(280), nullable=False, unique=True, index=True)

    # External catalog ID (e.g. TMDB's movie/tv id), used by the ingestion
    # pipeline (app/services/ingestion_service.py) to upsert idempotently —
    # re-running a sync updates the existing row instead of duplicating it.
    # Nullable because titles can also be created manually/seeded without an
    # external source; unique-when-present is standard SQL NULL semantics
    # (multiple NULLs don't collide with a unique constraint).
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True, index=True)

    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    tagline: Mapped[str | None] = mapped_column(String(500), nullable=True)

    poster_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    backdrop_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # "release_date" for movies, "first air date" for TV shows — unified here
    # since every date-based filter (decade, year, upcoming) applies to both.
    release_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)

    original_language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    status: Mapped[TitleStatus] = mapped_column(
        String(20), nullable=False, default=TitleStatus.RELEASED
    )

    # Aggregate stats sourced from an external catalog (e.g. TMDB) — distinct
    # from `ratings`, which holds MovieRoulette's own users' scores.
    popularity: Mapped[float] = mapped_column(nullable=False, default=0.0, index=True)
    vote_average: Mapped[float] = mapped_column(nullable=False, default=0.0)
    vote_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    is_oscar_winner: Mapped[bool] = mapped_column(nullable=False, default=False)

    genres: Mapped[list["Genre"]] = relationship(  # noqa: F821
        secondary=title_genres, back_populates="titles", lazy="selectin"
    )
    credits: Mapped[list["Credit"]] = relationship(  # noqa: F821
        back_populates="title", cascade="all, delete-orphan", lazy="selectin"
    )
    availability: Mapped[list["TitleAvailability"]] = relationship(  # noqa: F821
        back_populates="title", cascade="all, delete-orphan", lazy="selectin"
    )

    __mapper_args__ = {
        "polymorphic_on": media_type,
        # Base rows are never inserted directly, but a "identity" type is
        # required by SQLAlchemy's polymorphic mapper configuration.
        "polymorphic_identity": "title",
    }

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"<Title id={self.id} title={self.title!r} media_type={self.media_type}>"


class Movie(Title):
    """Movie-specific fields, joined to their `titles` base row 1:1."""

    __tablename__ = "movies"

    title_id: Mapped[int] = mapped_column(
        ForeignKey("titles.id", ondelete="CASCADE"), primary_key=True
    )

    runtime_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    budget: Mapped[int | None] = mapped_column(nullable=True)
    revenue: Mapped[int | None] = mapped_column(nullable=True)

    __mapper_args__ = {"polymorphic_identity": MediaType.MOVIE.value}


class TVShow(Title):
    """TV-show-specific fields, joined to their `titles` base row 1:1."""

    __tablename__ = "tv_shows"

    title_id: Mapped[int] = mapped_column(
        ForeignKey("titles.id", ondelete="CASCADE"), primary_key=True
    )

    number_of_seasons: Mapped[int | None] = mapped_column(Integer, nullable=True)
    number_of_episodes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    episode_runtime_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_air_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    in_production: Mapped[bool] = mapped_column(nullable=False, default=False)

    __mapper_args__ = {"polymorphic_identity": MediaType.TV_SHOW.value}
