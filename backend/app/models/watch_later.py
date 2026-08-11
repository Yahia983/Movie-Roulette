"""Watch Later: a user's queue of titles they intend to watch.

Kept as its own table rather than reusing Favorite with a "type" flag —
favoriting and queuing are semantically different actions (a title can be
both, or either, independently) and keeping them separate avoids a
compound-key-plus-discriminator table that's harder to index and query.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.title import Title  # noqa: F401


class WatchLaterItem(Base):
    __tablename__ = "watch_later_items"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    title_id: Mapped[int] = mapped_column(
        ForeignKey("titles.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    title: Mapped["Title"] = relationship(lazy="joined")  # noqa: F821
