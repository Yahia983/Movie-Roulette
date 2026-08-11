"""Password hashing and JWT helpers.

Why this exists as its own module: authentication primitives (hashing scheme,
token signing) are the highest-consequence code in the app to get subtly
wrong. Isolating them means there is exactly one place that knows how a
password is hashed or a token is signed, which makes future algorithm
rotations (e.g. bcrypt -> argon2) a one-file change instead of a grep-and-pray
across the codebase.
"""

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()

# Talking to the `bcrypt` library directly rather than through passlib:
# passlib has been unmaintained since 2020 and its bcrypt backend detection
# breaks on modern bcrypt releases (it probes an internal `__about__`
# attribute that newer bcrypt no longer exposes). bcrypt itself is actively
# maintained, and hashing/verifying directly is only a few lines either way.
_BCRYPT_ROUNDS = 12

# bcrypt silently truncates/errors past 72 bytes; this is a defensive
# backstop (the primary control is the max_length on the password field in
# schemas/user.py).
_MAX_PASSWORD_BYTES = 72


class TokenType(StrEnum):
    """Distinguishes access vs. refresh tokens inside the JWT payload.

    Why: without an explicit `type` claim, a leaked long-lived refresh token
    could be replayed as if it were a short-lived access token. Checking this
    claim on every protected endpoint closes that gap.
    """

    ACCESS = "access"
    REFRESH = "refresh"


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password for storage. Never store plaintext, ever."""
    password_bytes = plain_password.encode("utf-8")[:_MAX_PASSWORD_BYTES]
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=_BCRYPT_ROUNDS))
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plaintext password against a stored hash."""
    password_bytes = plain_password.encode("utf-8")[:_MAX_PASSWORD_BYTES]
    try:
        return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))
    except ValueError:
        # A malformed stored hash should fail closed, never raise into the
        # caller and risk being mishandled as "authenticated".
        return False


def _create_token(subject: str, expires_delta: timedelta, token_type: TokenType) -> str:
    """Build and sign a JWT for the given subject (typically the user id)."""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type.value,
        "iat": now,
        "exp": now + expires_delta,
    }
    # jose's `jwt` module ships without type stubs, so mypy sees `.encode()`
    # as returning Any; the explicit `str(...)` gives mypy (and any caller) a
    # concrete guarantee without changing runtime behavior — python-jose
    # always returns a str here.
    return str(jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM))


def create_access_token(subject: str) -> str:
    """Create a short-lived access token used to authenticate API requests."""
    return _create_token(
        subject,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        TokenType.ACCESS,
    )


def create_refresh_token(subject: str) -> str:
    """Create a long-lived refresh token used only to mint new access tokens."""
    return _create_token(
        subject,
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        TokenType.REFRESH,
    )


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    """Decode and validate a JWT, enforcing the expected token type.

    Raises jose.JWTError (or a ValueError for a type mismatch) on any failure;
    callers are expected to translate this into an HTTP 401.
    """
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    if payload.get("type") != expected_type.value:
        raise JWTError(f"Expected a {expected_type.value} token, got {payload.get('type')}")
    # Same untyped-library situation as `_create_token` above.
    return dict(payload)
