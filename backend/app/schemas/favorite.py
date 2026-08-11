"""Favorite / watch-later schemas — structurally identical, kept as separate
classes so the API contract for each feature can evolve independently."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.title import TitleSummary


class FavoriteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: TitleSummary
    created_at: datetime


class WatchLaterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: TitleSummary
    created_at: datetime
