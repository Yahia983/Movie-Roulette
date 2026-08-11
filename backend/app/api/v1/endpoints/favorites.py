"""Favorites endpoints — a user's saved titles."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.favorite import FavoriteRead
from app.schemas.pagination import Page, PageParams
from app.services import library_service

router = APIRouter()


@router.get("", response_model=Page[FavoriteRead])
async def list_favorites(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Page[FavoriteRead]:
    page_params = PageParams(page=page, page_size=page_size)
    items, total = await library_service.list_favorites(db, current_user.id, page_params)
    return Page[FavoriteRead](
        items=[FavoriteRead.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        has_next=page_params.offset + len(items) < total,
    )


@router.put("/{title_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_favorite(
    title_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """PUT (not POST) because this is idempotent — favoriting the same title
    twice is a no-op, matching PUT's semantics."""
    try:
        await library_service.add_favorite(db, current_user.id, title_id)
    except library_service.TitleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{title_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    title_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await library_service.remove_favorite(db, current_user.id, title_id)
