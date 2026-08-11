"""Favorites, watch-later, ratings, and viewing-history business logic.

Grouped into one module (rather than four near-empty files) because these
four features share the same shape — a user's relationship to a title — and
keeping them together makes the parallel structure obvious rather than
scattering four near-duplicate CRUD modules across the codebase.
"""

from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.favorite import Favorite
from app.models.rating import Rating
from app.models.title import Title
from app.models.viewing_history import ViewingHistoryEntry
from app.models.watch_later import WatchLaterItem
from app.schemas.pagination import PageParams
from app.schemas.rating import RatingCreate


async def _title_exists(db: AsyncSession, title_id: int) -> bool:
    return (await db.get(Title, title_id)) is not None


class TitleNotFoundError(Exception):
    """Raised when an operation references a title_id that doesn't exist."""


# --- Favorites ---


async def add_favorite(db: AsyncSession, user_id: int, title_id: int) -> Favorite:
    if not await _title_exists(db, title_id):
        raise TitleNotFoundError(f"No title with id {title_id}.")

    existing = await db.get(Favorite, (user_id, title_id))
    if existing is not None:
        return existing  # Idempotent: favoriting twice is a no-op, not an error.

    favorite = Favorite(user_id=user_id, title_id=title_id)
    db.add(favorite)
    await db.commit()
    await db.refresh(favorite)
    return favorite


async def remove_favorite(db: AsyncSession, user_id: int, title_id: int) -> None:
    await db.execute(
        delete(Favorite).where(Favorite.user_id == user_id, Favorite.title_id == title_id)
    )
    await db.commit()


async def list_favorites(
    db: AsyncSession, user_id: int, page_params: PageParams
) -> tuple[list[Favorite], int]:
    base = select(Favorite).where(Favorite.user_id == user_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    stmt = (
        base.order_by(Favorite.created_at.desc())
        .offset(page_params.offset)
        .limit(page_params.page_size)
    )
    items = (await db.execute(stmt)).scalars().all()
    return list(items), total


# --- Watch later ---


async def add_watch_later(db: AsyncSession, user_id: int, title_id: int) -> WatchLaterItem:
    if not await _title_exists(db, title_id):
        raise TitleNotFoundError(f"No title with id {title_id}.")

    existing = await db.get(WatchLaterItem, (user_id, title_id))
    if existing is not None:
        return existing

    item = WatchLaterItem(user_id=user_id, title_id=title_id)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def remove_watch_later(db: AsyncSession, user_id: int, title_id: int) -> None:
    await db.execute(
        delete(WatchLaterItem).where(
            WatchLaterItem.user_id == user_id, WatchLaterItem.title_id == title_id
        )
    )
    await db.commit()


async def list_watch_later(
    db: AsyncSession, user_id: int, page_params: PageParams
) -> tuple[list[WatchLaterItem], int]:
    base = select(WatchLaterItem).where(WatchLaterItem.user_id == user_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    stmt = (
        base.order_by(WatchLaterItem.created_at.desc())
        .offset(page_params.offset)
        .limit(page_params.page_size)
    )
    items = (await db.execute(stmt)).scalars().all()
    return list(items), total


# --- Ratings ---


async def upsert_rating(
    db: AsyncSession, user_id: int, title_id: int, payload: RatingCreate
) -> Rating:
    """Create or update a user's rating for a title — a user has at most one
    rating per title, so this is an upsert rather than an insert-only op."""
    if not await _title_exists(db, title_id):
        raise TitleNotFoundError(f"No title with id {title_id}.")

    rating = await db.get(Rating, (user_id, title_id))
    if rating is None:
        rating = Rating(user_id=user_id, title_id=title_id)
        db.add(rating)

    rating.score = payload.score
    rating.review_text = payload.review_text
    rating.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(rating)
    return rating


async def delete_rating(db: AsyncSession, user_id: int, title_id: int) -> None:
    await db.execute(delete(Rating).where(Rating.user_id == user_id, Rating.title_id == title_id))
    await db.commit()


# --- Viewing history ---


async def record_view(db: AsyncSession, user_id: int, title_id: int) -> ViewingHistoryEntry:
    """Log a viewing event. Called when a user opens a title's detail page —
    every open is its own event, so repeat views are expected, not deduped."""
    if not await _title_exists(db, title_id):
        raise TitleNotFoundError(f"No title with id {title_id}.")

    entry = ViewingHistoryEntry(user_id=user_id, title_id=title_id)
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def list_recently_viewed(
    db: AsyncSession, user_id: int, page_params: PageParams
) -> tuple[list[ViewingHistoryEntry], int]:
    base = select(ViewingHistoryEntry).where(ViewingHistoryEntry.user_id == user_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    stmt = (
        base.order_by(ViewingHistoryEntry.viewed_at.desc())
        .offset(page_params.offset)
        .limit(page_params.page_size)
    )
    items = (await db.execute(stmt)).scalars().all()
    return list(items), total
