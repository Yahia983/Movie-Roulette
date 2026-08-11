"""Title (movie/TV show) schemas.

Two levels of detail per type, matching how they're actually used: a
`Summary` shape for browse/search/grid pages (cheap to serialize, no
credits/availability joins), and a `Detail` shape for the movie/TV detail
pages that needs everything at once. This mirrors the spec's distinction
between browsing the library and viewing a Movie/TV Detail Page.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict

from app.models.enums import MediaType, TitleStatus
from app.schemas.genre import GenreRead
from app.schemas.person import CreditRead


class TitleSummary(BaseModel):
    """Compact representation for grids, search results, and the roulette result."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    media_type: MediaType
    title: str
    slug: str
    poster_path: str | None
    backdrop_path: str | None
    release_date: date | None
    popularity: float
    vote_average: float
    genres: list[GenreRead]


class StreamingAvailabilityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    region: str
    watch_url: str | None
    streaming_service: "StreamingServiceRead"


class StreamingServiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    logo_path: str | None


class TitleDetailBase(BaseModel):
    """Fields shared by MovieDetail and TVShowDetail."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    media_type: MediaType
    title: str
    slug: str
    overview: str | None
    tagline: str | None
    poster_path: str | None
    backdrop_path: str | None
    release_date: date | None
    original_language: str | None
    status: TitleStatus
    popularity: float
    vote_average: float
    vote_count: int
    is_oscar_winner: bool
    genres: list[GenreRead]
    credits: list[CreditRead]
    availability: list[StreamingAvailabilityRead]


class MovieDetail(TitleDetailBase):
    runtime_minutes: int | None
    budget: int | None
    revenue: int | None


class TVShowDetail(TitleDetailBase):
    number_of_seasons: int | None
    number_of_episodes: int | None
    episode_runtime_minutes: int | None
    last_air_date: date | None
    in_production: bool


StreamingAvailabilityRead.model_rebuild()
