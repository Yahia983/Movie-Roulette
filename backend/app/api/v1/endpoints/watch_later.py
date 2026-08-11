"""Watch Later endpoints — structurally parallel to favorites.py."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.favorite import WatchLaterRead
from app.schemas.pagination import Page, PageParams
from app.services import library_service

router = APIRouter()


@router.get("", response_model=Page[WatchLaterRead])
async def list_watch_later(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Page[WatchLaterRead]:
    page_params = PageParams(page=page, page_size=page_size)
    items, total = await library_service.list_watch_later(db, current_user.id, page_params)
    return Page[WatchLaterRead](
        items=[WatchLaterRead.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        has_next=page_params.offset + len(items) < total,
    )


@router.put("/{title_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_watch_later(
    title_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await library_service.add_watch_later(db, current_user.id, title_id)
    except library_service.TitleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{title_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_watch_later(
    title_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await library_service.remove_watch_later(db, current_user.id, title_id)
