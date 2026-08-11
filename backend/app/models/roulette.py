"""Roulette spins: a record of each roulette engine invocation and its result.

Why persist this at all, rather than treating roulette as stateless: it's
the foundation for two things later phases need — "don't show me the same
result twice in a row" and feeding actual usage back into the Version 2
recommendation system (which filter combinations lead to favorited results).
Anonymous (logged-out) spins are supported via a nullable user_id.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.title import Title  # noqa: F401


class RouletteSpin(Base):
    __tablename__ = "roulette_spins"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # The filter combination the user selected (mood, genre, runtime bounds,
    # decade, etc.) — stored as JSON since the filter shape is expected to
    # evolve (per the spec's "Version 2" recommendation roadmap) without
    # needing a schema migration every time a new filter is added.
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    result_title_id: Mapped[int | None] = mapped_column(
        ForeignKey("titles.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    result_title: Mapped["Title | None"] = relationship(lazy="joined")  # noqa: F821
