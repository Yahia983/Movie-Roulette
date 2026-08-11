"""Viewing history: a log of titles a user has viewed/opened.

Unlike Favorite/WatchLaterItem, this is NOT a composite-primary-key table —
a user can view the same title multiple times, and each viewing is its own
event (useful for "recently viewed," future recommendation signals, and
distinguishing "viewed the detail page" from "marked as watched").
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.title import Title  # noqa: F401


class ViewingHistoryEntry(Base):
    __tablename__ = "viewing_history"
    __table_args__ = (
        # "recently viewed" always queries by user ordered by recency —
        # this composite index serves that query directly without a sort.
        Index("ix_viewing_history_user_viewed_at", "user_id", "viewed_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title_id: Mapped[int] = mapped_column(
        ForeignKey("titles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    viewed_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    title: Mapped["Title"] = relationship(lazy="joined")  # noqa: F821
