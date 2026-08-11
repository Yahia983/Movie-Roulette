"""Collection schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.title import TitleSummary


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=1000)
    is_public: bool = False


class CollectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=1000)
    is_public: bool | None = None


class CollectionItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: TitleSummary
    position: int
    added_at: datetime


class CollectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    is_public: bool
    created_at: datetime
    items: list[CollectionItemRead]


class CollectionSummary(BaseModel):
    """Lightweight shape for a user's list of collections (no items)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    is_public: bool
    created_at: datetime
