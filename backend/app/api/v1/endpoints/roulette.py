"""The roulette engine endpoint — the app's signature feature.

Works for both anonymous and logged-in users (per the spec: this should be
usable immediately, no signup wall) via `get_current_user_optional`; spins
are still logged either way (with a null user_id when anonymous) so usage
data accumulates from day one for the future recommendation system.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_optional
from app.db.session import get_db
from app.models.user import User
from app.schemas.roulette import RouletteSpinRequest, RouletteSpinResult
from app.schemas.title import TitleSummary
from app.services import roulette_service

router = APIRouter()


@router.post("/spin", response_model=RouletteSpinResult)
async def spin_roulette(
    payload: RouletteSpinRequest,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> RouletteSpinResult:
    """Run one roulette spin against the given filter combination."""
    selected, candidate_count = await roulette_service.spin(
        db, payload.filters, current_user.id if current_user else None
    )
    return RouletteSpinResult(
        result=TitleSummary.model_validate(selected) if selected else None,
        filters_applied=payload.filters,
        candidate_count=candidate_count,
    )
