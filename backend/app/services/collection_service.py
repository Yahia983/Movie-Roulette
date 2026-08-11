"""Collection (user-curated lists) business logic, including ownership checks.

Ownership enforcement lives here rather than in the router: every collection
mutation needs "does this collection belong to this user" checked before it
touches data, and centralizing it means that check can't be forgotten on a
future new endpoint that calls into this service.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collection import Collection, CollectionItem
from app.models.title import Title
from app.schemas.collection import CollectionCreate, CollectionUpdate
from app.schemas.pagination import PageParams


class CollectionNotFoundError(Exception):
    """Raised when a collection doesn't exist or doesn't belong to the user."""


class TitleNotFoundError(Exception):
    """Raised when adding a nonexistent title_id to a collection."""


async def _get_owned_collection(db: AsyncSession, collection_id: int, user_id: int) -> Collection:
    collection = await db.get(Collection, collection_id)
    if collection is None or collection.user_id != user_id:
        raise CollectionNotFoundError(f"No collection with id {collection_id} for this user.")
    return collection


async def create_collection(
    db: AsyncSession, user_id: int, payload: CollectionCreate
) -> Collection:
    collection = Collection(user_id=user_id, **payload.model_dump())
    db.add(collection)
    await db.commit()
    await db.refresh(collection)
    return collection


async def list_collections(
    db: AsyncSession, user_id: int, page_params: PageParams
) -> tuple[list[Collection], int]:
    base = select(Collection).where(Collection.user_id == user_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    stmt = (
        base.order_by(Collection.created_at.desc())
        .offset(page_params.offset)
        .limit(page_params.page_size)
    )
    items = (await db.execute(stmt)).scalars().all()
    return list(items), total


async def get_collection(db: AsyncSession, collection_id: int, user_id: int) -> Collection:
    """Fetch a collection with its items eagerly loaded for the detail view."""
    stmt = select(Collection).where(Collection.id == collection_id)
    collection = (await db.execute(stmt)).scalar_one_or_none()
    if collection is None or collection.user_id != user_id:
        raise CollectionNotFoundError(f"No collection with id {collection_id} for this user.")
    return collection


async def update_collection(
    db: AsyncSession, collection_id: int, user_id: int, payload: CollectionUpdate
) -> Collection:
    collection = await _get_owned_collection(db, collection_id, user_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(collection, field, value)
    await db.commit()
    await db.refresh(collection)
    return collection


async def delete_collection(db: AsyncSession, collection_id: int, user_id: int) -> None:
    collection = await _get_owned_collection(db, collection_id, user_id)
    await db.delete(collection)
    await db.commit()


async def add_item(
    db: AsyncSession, collection_id: int, user_id: int, title_id: int
) -> CollectionItem:
    collection = await _get_owned_collection(db, collection_id, user_id)

    if (await db.get(Title, title_id)) is None:
        raise TitleNotFoundError(f"No title with id {title_id}.")

    existing = next((i for i in collection.items if i.title_id == title_id), None)
    if existing is not None:
        return existing  # Idempotent: adding twice is a no-op.

    next_position = len(collection.items)
    item = CollectionItem(collection_id=collection_id, title_id=title_id, position=next_position)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def remove_item(db: AsyncSession, collection_id: int, user_id: int, title_id: int) -> None:
    collection = await _get_owned_collection(db, collection_id, user_id)
    item = next((i for i in collection.items if i.title_id == title_id), None)
    if item is not None:
        await db.delete(item)
        await db.commit()
