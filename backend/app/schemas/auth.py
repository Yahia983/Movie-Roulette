"""Authentication request/response schemas."""

from pydantic import BaseModel


class LoginRequest(BaseModel):
    """Login accepts email OR username in the same field to keep the UX
    forgiving — the service layer decides which one it matches against."""

    identifier: str
    password: str


class TokenResponse(BaseModel):
    """Returned on successful login/refresh. `token_type` is always "bearer"
    but included explicitly since it's part of the OAuth2-style contract
    clients (and Swagger UI's built-in auth) expect."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
