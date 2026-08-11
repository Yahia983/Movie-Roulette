"""Favorites: a user's saved titles.

A dedicated table with a composite primary key (rather than a JSON array of
title IDs on User) so favoriting is indexable, orderable by recency, and
joinable directly against `titles` for a favorites-list query.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.title import Title  # noqa: F401


class Favorite(Base):
    __tablename__ = "favorites"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    title_id: Mapped[int] = mapped_column(
        ForeignKey("titles.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    title: Mapped["Title"] = relationship(lazy="joined")  # noqa: F821
