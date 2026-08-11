"""Browsing, searching, and filtering the title library.

One shared implementation for movies and TV shows (parameterized by
`media_type`) rather than duplicating near-identical query-building code in
two places — the filter set (genre, rating, runtime, decade, language) is
defined once here and reused by both `/movies` and `/tv-shows`.
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MediaType
from app.models.genre import Genre
from app.models.title import Title
from app.schemas.pagination import PageParams


class SortBy(StrEnum):
    POPULARITY = "popularity"
    RATING = "rating"
    RELEASE_DATE = "release_date"
    TITLE = "title"


@dataclass(slots=True)
class TitleFilters:
    """Query parameters accepted by the browse/search endpoints.

    A plain dataclass (not the Pydantic request schema itself) so the
    service layer's public interface doesn't depend on FastAPI/Pydantic
    request parsing — keeping it callable from anywhere, including the
    roulette service, which builds this same filter set from different input.
    """

    search: str | None = None
    genre_ids: list[int] | None = None
    min_rating: float | None = None
    max_runtime_minutes: int | None = None
    min_runtime_minutes: int | None = None
    release_date_from: date | None = None
    release_date_to: date | None = None
    original_language: str | None = None
    sort_by: SortBy = SortBy.POPULARITY


def _apply_filters(stmt: "Select[tuple[Title]]", filters: TitleFilters) -> "Select[tuple[Title]]":
    """Apply the shared WHERE-clause filters to a base titles query."""
    if filters.search:
        # Case-insensitive substring match. A dedicated search index
        # (Postgres full-text or a future vector/semantic search per the
        # spec's Version 2 roadmap) replaces this once search volume
        # justifies it; this is the correct, simple default for now.
        stmt = stmt.where(Title.title.ilike(f"%{filters.search}%"))

    if filters.genre_ids:
        stmt = stmt.where(Title.genres.any(Genre.id.in_(filters.genre_ids)))

    if filters.min_rating is not None:
        stmt = stmt.where(Title.vote_average >= filters.min_rating)

    if filters.release_date_from is not None:
        stmt = stmt.where(Title.release_date >= filters.release_date_from)

    if filters.release_date_to is not None:
        stmt = stmt.where(Title.release_date <= filters.release_date_to)

    if filters.original_language:
        stmt = stmt.where(Title.original_language == filters.original_language)

    return stmt


def _apply_sort(stmt: "Select[tuple[Title]]", sort_by: SortBy) -> "Select[tuple[Title]]":
    match sort_by:
        case SortBy.POPULARITY:
            return stmt.order_by(Title.popularity.desc())
        case SortBy.RATING:
            return stmt.order_by(Title.vote_average.desc())
        case SortBy.RELEASE_DATE:
            return stmt.order_by(Title.release_date.desc())
        case SortBy.TITLE:
            return stmt.order_by(Title.title.asc())
        case _:
            return stmt.order_by(Title.popularity.desc())


async def list_titles(
    db: AsyncSession,
    media_type: MediaType,
    filters: TitleFilters,
    page_params: PageParams,
) -> tuple[list[Title], int]:
    """Return (page of results, total matching count) for a browse/search query.

    Thin wrapper around `_query_titles` that exists for the public,
    UI-facing API — bounded to the page sizes `PageParams` allows (max 100).
    """
    return await _query_titles(
        db, media_type, filters, offset=page_params.offset, limit=page_params.page_size
    )


async def list_titles_for_candidates(
    db: AsyncSession,
    media_type: MediaType,
    filters: TitleFilters,
    limit: int,
) -> tuple[list[Title], int]:
    """Like `list_titles`, but for internal callers (the roulette engine)
    that need a larger candidate pool than the public API's page-size cap
    allows. Kept separate from `list_titles` rather than loosening
    `PageParams`' limit, since that limit is a deliberate UI/API contract
    that internal service-to-service calls shouldn't be able to bypass by
    accident — this function makes the bypass explicit and named.
    """
    return await _query_titles(db, media_type, filters, offset=0, limit=limit)


async def _query_titles(
    db: AsyncSession,
    media_type: MediaType,
    filters: TitleFilters,
    offset: int,
    limit: int,
) -> tuple[list[Title], int]:
    base_stmt = select(Title).where(Title.media_type == media_type.value)
    base_stmt = _apply_filters(base_stmt, filters)

    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    results_stmt = _apply_sort(base_stmt, filters.sort_by)
    results_stmt = results_stmt.offset(offset).limit(limit)

    items = (await db.execute(results_stmt)).scalars().all()
    return list(items), total


async def get_title_by_id(
    db: AsyncSession, title_id: int, model: type[Title] = Title
) -> Title | None:
    """Fetch a single title by primary key, using the concrete `Movie`/`TVShow`
    class when known so SQLAlchemy joins the subtype table in one query
    instead of a secondary lazy load per subclass-specific column."""
    return await db.get(model, title_id)


async def get_title_by_slug(
    db: AsyncSession, slug: str, media_type: MediaType, model: type[Title] = Title
) -> Title | None:
    """Fetch a single title by slug, scoped to the expected media type so
    `/movies/{slug}` can never accidentally resolve a TV show and vice versa.

    Callers that know the concrete subclass (movies.py passes `Movie`,
    tv_shows.py passes `TVShow`) should pass it via `model` — querying the
    concrete subclass makes SQLAlchemy join `titles` with `movies`/`tv_shows`
    in a single statement, rather than lazily loading the subtype-specific
    columns in a second query per row (which fails in an async context
    outside a fresh await).
    """
    stmt = select(model).where(Title.slug == slug, Title.media_type == media_type.value)
    return (await db.execute(stmt)).scalar_one_or_none()
