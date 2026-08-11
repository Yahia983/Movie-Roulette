"""Rating schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.title import TitleSummary


class RatingCreate(BaseModel):
    score: int = Field(ge=1, le=10)
    review_text: str | None = Field(default=None, max_length=5000)


class RatingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score: int
    review_text: str | None
    created_at: datetime
    updated_at: datetime
    title: TitleSummary
