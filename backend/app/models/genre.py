"""Genre reference data — shared by both movies and TV shows."""

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.title import Title  # noqa: F401


class Genre(Base):
    """A genre tag (Action, Comedy, Documentary, ...).

    Deliberately a small, denormalized reference table rather than a fixed
    enum: genres are curated editorial data that occasionally gets added to
    (e.g. "Anime" as its own filter per the roulette spec) without a code
    deploy — a migration to seed one new row is much lighter than a schema
    migration to extend an enum type.
    """

    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    # TMDB's genre IDs are a small fixed set (e.g. 28 = Action) — mapping
    # against them lets the ingestion pipeline attach genres to synced
    # titles without a name-matching heuristic.
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)

    titles: Mapped[list["Title"]] = relationship(  # noqa: F821
        secondary="title_genres", back_populates="genres"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Genre id={self.id} name={self.name!r}>"
