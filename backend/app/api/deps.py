"""Shared FastAPI dependencies: current-user extraction from a JWT bearer token.

Why this lives in its own `deps.py` rather than inside each endpoints module:
every protected endpoint across every feature (favorites, ratings,
collections, roulette history) needs the exact same "who is making this
request" logic. One dependency function, reused via `Depends(...)`, means
that logic is defined and audited in exactly one place.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenType, decode_token
from app.db.session import get_db
from app.models.user import User

# tokenUrl points at the login endpoint purely so Swagger UI's "Authorize"
# button knows where to send credentials — this app issues tokens via JSON,
# not the OAuth2 password-form flow, so the form itself is never used.
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials.",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    token: str | None = Depends(_oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the authenticated User from a bearer access token.

    Raises 401 for any failure mode (missing token, malformed token, wrong
    token type, unknown user, deactivated account) — deliberately without
    distinguishing *why* in the response body, so the API never gives an
    attacker a signal about which failure mode they hit.
    """
    if token is None:
        raise _CREDENTIALS_ERROR

    try:
        payload = decode_token(token, expected_type=TokenType.ACCESS)
        user_id = int(payload["sub"])
    except (JWTError, ValueError, KeyError) as exc:
        raise _CREDENTIALS_ERROR from exc

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise _CREDENTIALS_ERROR

    return user


async def get_current_user_optional(
    token: str | None = Depends(_oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Like `get_current_user`, but returns None instead of raising.

    Used by endpoints that behave differently for logged-in vs. anonymous
    users without requiring auth outright — e.g. the roulette endpoint,
    which anonymous users can use but which personalizes for logged-in ones.
    """
    if token is None:
        return None
    try:
        return await get_current_user(token=token, db=db)
    except HTTPException:
        return None


# Re-exported so endpoint modules don't need to import `select`/`AsyncSession`
# just to type-hint the common `db: AsyncSession = Depends(get_db)` pattern.
__all__ = ["get_current_user", "get_current_user_optional", "get_db", "select"]
