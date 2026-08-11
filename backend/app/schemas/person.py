"""Person and credit schemas."""

from datetime import date

from pydantic import BaseModel, ConfigDict

from app.models.enums import CreditDepartment


class PersonSummary(BaseModel):
    """Lightweight person representation embedded in credit lists."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    profile_path: str | None


class PersonDetail(PersonSummary):
    """Full person page representation."""

    biography: str | None
    birth_date: date | None


class CreditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    department: CreditDepartment
    character_name: str | None
    display_order: int
    person: PersonSummary
