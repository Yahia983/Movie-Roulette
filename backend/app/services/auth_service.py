"""Authentication business logic.

Kept out of the router entirely: the router's job is to translate HTTP <->
these functions, not to know how passwords are checked or duplicate emails
are detected. That separation is what makes this logic unit-testable without
an HTTP client.
"""

from jose import JWTError
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import TokenResponse
from app.schemas.user import UserCreate


class AuthError(Exception):
    """Raised for any authentication failure. The API layer maps this to a
    generic 401/409 without leaking which specific check failed."""


async def register_user(db: AsyncSession, payload: UserCreate) -> User:
    """Create a new user account.

    Checks email and username uniqueness explicitly (rather than relying
    solely on the DB unique constraint + catching an IntegrityError) so we
    can return a clear, specific error message before ever touching the
    database.
    """
    existing = await db.execute(
        select(User).where(or_(User.email == payload.email, User.username == payload.username))
    )
    if existing.scalar_one_or_none() is not None:
        raise AuthError("An account with that email or username already exists.")

    user = User(
        email=payload.email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, identifier: str, password: str) -> User:
    """Verify credentials (matching identifier against email OR username) and
    return the User, or raise AuthError."""
    result = await db.execute(
        select(User).where(or_(User.email == identifier, User.username == identifier))
    )
    user = result.scalar_one_or_none()

    # Deliberately run verify_password even when no user was found, hashing
    # against a dummy value, so the response time doesn't leak whether the
    # identifier exists (a timing side-channel for account enumeration).
    if user is None:
        hash_password(password)
        raise AuthError("Incorrect email/username or password.")

    if not verify_password(password, user.hashed_password):
        raise AuthError("Incorrect email/username or password.")

    if not user.is_active:
        raise AuthError("This account has been deactivated.")

    return user


def issue_tokens(user: User) -> TokenResponse:
    """Mint a fresh access + refresh token pair for a user."""
    subject = str(user.id)
    return TokenResponse(
        access_token=create_access_token(subject),
        refresh_token=create_refresh_token(subject),
    )


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> TokenResponse:
    """Exchange a valid refresh token for a new access + refresh token pair.

    Issues a *new* refresh token too (rotation) rather than reusing the old
    one — standard practice that limits the blast radius of a leaked refresh
    token to a single use.
    """
    try:
        payload = decode_token(refresh_token, expected_type=TokenType.REFRESH)
        user_id = int(payload["sub"])
    except (JWTError, ValueError, KeyError) as exc:
        raise AuthError("Invalid or expired refresh token.") from exc

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthError("Invalid or expired refresh token.")

    return issue_tokens(user)
