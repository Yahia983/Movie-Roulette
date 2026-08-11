"""Genre schema."""

from pydantic import BaseModel, ConfigDict


class GenreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
