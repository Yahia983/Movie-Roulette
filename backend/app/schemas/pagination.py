"""Generic pagination request/response shapes, shared by every list endpoint.

A single generic `Page[T]` (rather than each endpoint hand-rolling its own
{items, total, ...} response model) keeps the API's pagination contract
identical everywhere, which matters for a frontend building one reusable
"infinite scroll" component per the spec instead of one per endpoint.
"""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageParams(BaseModel):
    """Common query parameters accepted by every paginated list endpoint."""

    page: int = Field(default=1, ge=1, description="1-indexed page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class Page(BaseModel, Generic[T]):
    """A single page of results plus enough metadata to render pagination
    controls or drive infinite scroll without a separate count endpoint."""

    items: list[T]
    total: int
    page: int
    page_size: int
    has_next: bool
