"""User-facing request/response schemas.

Why separate Create/Read/Update models instead of one shared model: `UserCreate`
must accept a plaintext password (and never a hashed one); `UserRead` must
NEVER include `hashed_password` at all, at the type level, so it's impossible
to accidentally leak a password hash by returning an ORM object through the
wrong schema. This separation is a security boundary, not just style.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    """Payload for registering a new account."""

    email: EmailStr
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_must_be_reasonably_strong(cls, value: str) -> str:
        """Minimal strength check at the API boundary.

        Deliberately not a strict "must contain 1 uppercase/1 symbol/..."
        rule — those rules push users toward predictable patterns (e.g.
        "Password1!") without meaningfully improving entropy. Length is the
        strongest practical signal; we just also reject all-whitespace input.
        """
        if not value.strip():
            raise ValueError("Password cannot be blank or whitespace only.")
        return value


class UserUpdate(BaseModel):
    """Payload for updating the current user's own profile. All fields optional."""

    display_name: str | None = Field(default=None, max_length=100)
    avatar_path: str | None = Field(default=None, max_length=500)


class UserRead(BaseModel):
    """Public-safe user representation — never includes hashed_password."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    username: str
    display_name: str | None
    avatar_path: str | None
    is_verified: bool
    created_at: datetime
