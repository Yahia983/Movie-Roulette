"""Streaming availability: which service a title can be watched on, and
where — availability is region-specific, which is why this isn't a simple
title<->service many-to-many.
"""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.title import Title  # noqa: F401


class StreamingService(Base):
    """A streaming provider (Netflix, Max, Hulu, ...)."""

    __tablename__ = "streaming_services"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    logo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)


class TitleAvailability(Base):
    """Where a specific title can currently be streamed, per region.

    Region is part of the row (not a separate table keyed by service alone)
    because the same title/service pair can be available in one region and
    not another — this is real streaming-catalog behavior, not an edge case.
    """

    __tablename__ = "title_availability"
    __table_args__ = (
        UniqueConstraint(
            "title_id", "streaming_service_id", "region", name="uq_title_availability"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title_id: Mapped[int] = mapped_column(
        ForeignKey("titles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    streaming_service_id: Mapped[int] = mapped_column(
        ForeignKey("streaming_services.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # ISO 3166-1 alpha-2 country code (e.g. "US", "GB").
    region: Mapped[str] = mapped_column(String(2), nullable=False, default="US")
    watch_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    title: Mapped["Title"] = relationship(back_populates="availability")  # noqa: F821
    streaming_service: Mapped["StreamingService"] = relationship(lazy="selectin")
