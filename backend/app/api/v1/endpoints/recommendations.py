"""Personalized recommendations — "Recommended for you" on the home page."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.title import TitleSummary
from app.services import recommendation_service

router = APIRouter()


@router.get("/for-you", response_model=list[TitleSummary])
async def get_for_you_recommendations(
    limit: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TitleSummary]:
    """Personalized picks based on the current user's favorites and ratings.

    Requires authentication — unlike the roulette engine, which is
    deliberately usable anonymously, a "for you" feed is meaningless
    without a user history to base it on.
    """
    recommendations = await recommendation_service.get_recommendations_for_user(
        db, current_user.id, limit=limit
    )
    return [TitleSummary.model_validate(t) for t in recommendations]
