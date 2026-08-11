"""Genre listing — used to populate filter UI (browse filters, roulette filters)."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.genre import Genre
from app.schemas.genre import GenreRead

router = APIRouter()


@router.get("", response_model=list[GenreRead])
async def list_genres(db: AsyncSession = Depends(get_db)) -> list[GenreRead]:
    """Return all genres, alphabetically. Small, mostly-static reference
    data — no pagination needed."""
    stmt = select(Genre).order_by(Genre.name.asc())
    genres = (await db.execute(stmt)).scalars().all()
    return [GenreRead.model_validate(g) for g in genres]
