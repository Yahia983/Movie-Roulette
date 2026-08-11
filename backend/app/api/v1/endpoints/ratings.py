"""Ratings endpoints — a user's own score/review for a title."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.rating import RatingCreate, RatingRead
from app.services import library_service

router = APIRouter()


@router.put("/{title_id}", response_model=RatingRead)
async def rate_title(
    title_id: int,
    payload: RatingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RatingRead:
    """Create or update the current user's rating for a title (upsert)."""
    try:
        rating = await library_service.upsert_rating(db, current_user.id, title_id, payload)
    except library_service.TitleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return RatingRead.model_validate(rating)


@router.delete("/{title_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rating(
    title_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await library_service.delete_rating(db, current_user.id, title_id)
