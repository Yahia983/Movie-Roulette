"""Recently-viewed endpoint."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.favorite import WatchLaterRead  # reused shape: {title, created_at}
from app.schemas.pagination import Page, PageParams
from app.services import library_service

router = APIRouter()


@router.get("", response_model=Page[WatchLaterRead])
async def list_recently_viewed(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Page[WatchLaterRead]:
    page_params = PageParams(page=page, page_size=page_size)
    items, total = await library_service.list_recently_viewed(db, current_user.id, page_params)
    # ViewingHistoryEntry has `viewed_at` not `created_at`; adapt to the
    # shared response shape at the boundary rather than adding a near-dupe schema.
    return Page[WatchLaterRead](
        items=[WatchLaterRead(title=i.title, created_at=i.viewed_at) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        has_next=page_params.offset + len(items) < total,
    )
