"""People (cast and crew) and their credits on titles."""

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import CreditDepartment

if TYPE_CHECKING:
    from app.models.title import Title  # noqa: F401


class Person(Base):
    """An actor, director, writer, or producer.

    Kept as one table across all roles (rather than separate Actor/Director
    tables) because a real person is frequently credited in multiple
    departments across different titles (an actor who also directs), and a
    "Person Page" per the spec needs to show all of it in one place.
    """

    __tablename__ = "people"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(280), nullable=False, unique=True, index=True)
    # Same rationale as Title.tmdb_id — enables idempotent upsert during sync.
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True, index=True)
    biography: Mapped[str | None] = mapped_column(String(5000), nullable=True)
    profile_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    credits: Mapped[list["Credit"]] = relationship(back_populates="person")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Person id={self.id} name={self.name!r}>"


class Credit(TimestampMixin, Base):
    """A single person's involvement in a single title.

    One row per (title, person, department) rather than a plain many-to-many
    table, because credits carry meaningful extra data — a character name
    for cast, a display order for billing — that a bare association table
    can't hold.
    """

    __tablename__ = "credits"

    id: Mapped[int] = mapped_column(primary_key=True)
    title_id: Mapped[int] = mapped_column(
        ForeignKey("titles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id: Mapped[int] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True
    )
    department: Mapped[CreditDepartment] = mapped_column(String(20), nullable=False)
    character_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Billing order, used to render "top billed cast" without a second query.
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    title: Mapped["Title"] = relationship(back_populates="credits")  # noqa: F821
    person: Mapped["Person"] = relationship(back_populates="credits", lazy="selectin")
