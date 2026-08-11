"""Roulette engine request/response schemas.

`RouletteFilters` covers the V1 filter set from the spec (mood, genre,
runtime, rating, decade, popularity tier, streaming service, and the
one-click preset categories like "Hidden Gems" / "Oscar Winners" / "Quick
Watch"). All fields are optional so any combination — including none, for
"Everything" — is valid.
"""

from datetime import date

from pydantic import BaseModel, Field

from app.models.enums import MediaType
from app.schemas.title import TitleSummary


class RouletteFilters(BaseModel):
    media_type: MediaType | None = None
    genre_ids: list[int] | None = Field(default=None, description="Match ANY of these genres")
    min_rating: float | None = Field(default=None, ge=0, le=10)
    max_runtime_minutes: int | None = Field(default=None, ge=1)
    min_runtime_minutes: int | None = Field(default=None, ge=1)
    decade: int | None = Field(default=None, description="e.g. 1990 for the 1990s")
    original_language: str | None = None
    streaming_service_id: int | None = None

    # One-click preset categories from the spec.
    hidden_gems: bool = Field(
        default=False, description="High rating, low popularity — under-the-radar picks"
    )
    oscar_winners: bool = False

    @property
    def decade_bounds(self) -> tuple[date, date] | None:
        """Convert a decade like 1990 into an inclusive [1990-01-01, 1999-12-31] range."""
        if self.decade is None:
            return None
        return date(self.decade, 1, 1), date(self.decade + 9, 12, 31)


class RouletteSpinRequest(BaseModel):
    filters: RouletteFilters = Field(default_factory=RouletteFilters)


class RouletteSpinResult(BaseModel):
    result: TitleSummary | None
    filters_applied: RouletteFilters
    candidate_count: int = Field(description="How many titles matched before random selection")
