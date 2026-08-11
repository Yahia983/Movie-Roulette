"""Collection endpoints: CRUD for a user's curated lists, plus item management."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.collection import (
    CollectionCreate,
    CollectionRead,
    CollectionSummary,
    CollectionUpdate,
)
from app.schemas.pagination import Page, PageParams
from app.services import collection_service

router = APIRouter()


@router.post("", response_model=CollectionRead, status_code=status.HTTP_201_CREATED)
async def create_collection(
    payload: CollectionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CollectionRead:
    collection = await collection_service.create_collection(db, current_user.id, payload)
    return CollectionRead.model_validate(collection)


@router.get("", response_model=Page[CollectionSummary])
async def list_collections(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Page[CollectionSummary]:
    page_params = PageParams(page=page, page_size=page_size)
    items, total = await collection_service.list_collections(db, current_user.id, page_params)
    return Page[CollectionSummary](
        items=[CollectionSummary.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        has_next=page_params.offset + len(items) < total,
    )


@router.get("/{collection_id}", response_model=CollectionRead)
async def get_collection(
    collection_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CollectionRead:
    try:
        collection = await collection_service.get_collection(db, collection_id, current_user.id)
    except collection_service.CollectionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return CollectionRead.model_validate(collection)


@router.patch("/{collection_id}", response_model=CollectionRead)
async def update_collection(
    collection_id: int,
    payload: CollectionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CollectionRead:
    try:
        collection = await collection_service.update_collection(
            db, collection_id, current_user.id, payload
        )
    except collection_service.CollectionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return CollectionRead.model_validate(collection)


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    collection_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await collection_service.delete_collection(db, collection_id, current_user.id)
    except collection_service.CollectionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/{collection_id}/items/{title_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_collection_item(
    collection_id: int,
    title_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await collection_service.add_item(db, collection_id, current_user.id, title_id)
    except collection_service.CollectionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except collection_service.TitleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{collection_id}/items/{title_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_collection_item(
    collection_id: int,
    title_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await collection_service.remove_item(db, collection_id, current_user.id, title_id)
    except collection_service.CollectionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
