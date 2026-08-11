"""TV show library endpoints — structurally identical to movies.py, kept as
a separate module (rather than a single parameterized router) because the
response model genuinely differs (TVShowDetail vs MovieDetail) and because
the URL prefix ("/tv-shows" vs "/movies") is a first-class part of the
public API contract that shouldn't be hidden behind shared routing magic.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_optional
from app.db.session import get_db
from app.models.enums import MediaType
from app.models.title import TVShow
from app.models.user import User
from app.schemas.pagination import Page, PageParams
from app.schemas.title import TitleSummary, TVShowDetail
from app.services import library_service, recommendation_service
from app.services.title_service import SortBy, TitleFilters, get_title_by_slug, list_titles

router = APIRouter()


@router.get("", response_model=Page[TitleSummary])
async def browse_tv_shows(
    search: str | None = Query(default=None, description="Free-text title search"),
    genre_ids: list[int] | None = Query(default=None),
    min_rating: float | None = Query(default=None, ge=0, le=10),
    release_date_from: date | None = None,
    release_date_to: date | None = None,
    original_language: str | None = None,
    sort_by: SortBy = SortBy.POPULARITY,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> Page[TitleSummary]:
    """Browse/search/filter TV shows. Powers the infinite-scroll library grid."""
    filters = TitleFilters(
        search=search,
        genre_ids=genre_ids,
        min_rating=min_rating,
        release_date_from=release_date_from,
        release_date_to=release_date_to,
        original_language=original_language,
        sort_by=sort_by,
    )
    page_params = PageParams(page=page, page_size=page_size)
    items, total = await list_titles(db, MediaType.TV_SHOW, filters, page_params)

    return Page[TitleSummary](
        items=[TitleSummary.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        has_next=page_params.offset + len(items) < total,
    )


@router.get("/{slug}", response_model=TVShowDetail)
async def get_tv_show(
    slug: str,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> TVShowDetail:
    """TV show detail page. Logs viewing history for authenticated users."""
    show = await get_title_by_slug(db, slug, MediaType.TV_SHOW, model=TVShow)
    if show is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TV show not found.")

    if current_user is not None:
        await library_service.record_view(db, current_user.id, show.id)

    return TVShowDetail.model_validate(show)


@router.get("/{slug}/similar", response_model=list[TitleSummary])
async def get_similar_tv_shows(
    slug: str,
    limit: int = Query(default=12, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> list[TitleSummary]:
    """ "More like this" — content-based recommendations (shared genres and
    cast/crew) for the TV show's detail page."""
    show = await get_title_by_slug(db, slug, MediaType.TV_SHOW, model=TVShow)
    if show is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TV show not found.")

    similar = await recommendation_service.get_similar_titles(db, show.id, limit=limit)
    return [TitleSummary.model_validate(t) for t in similar]
