"""Application configuration.

Why this exists: scattering `os.environ["X"]` calls across the codebase means
misconfiguration is only discovered when the misconfigured code path finally
runs — sometimes in production, sometimes never (silently wrong). Centralizing
config in one validated Pydantic model means the app refuses to start at all
if something required is missing or malformed. That failure mode is much
cheaper than a 3am page.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings, sourced from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Core app metadata ---
    PROJECT_NAME: str = "MovieRoulette"
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    # --- Security ---
    # Secret used to sign JWTs. MUST be overridden in every non-dev environment;
    # the dev default exists only so `uvicorn` can boot without a .env for local hacking.
    SECRET_KEY: str = Field(default="dev-only-insecure-secret-change-me")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # --- Database ---
    # Async URL used by the app at runtime (asyncpg driver).
    DATABASE_URL: str = (
        "postgresql+asyncpg://movieroulette:movieroulette@localhost:5432/movieroulette"
    )
    # Sync URL used only by Alembic, which does not support async drivers well.
    DATABASE_URL_SYNC: str = (
        "postgresql+psycopg2://movieroulette:movieroulette@localhost:5432/movieroulette"
    )
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    # --- Redis / caching ---
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_DEFAULT_TTL_SECONDS: int = 300

    # --- CORS ---
    # Explicit allow-list rather than "*" — the frontend is decoupled and served
    # from its own origin, so we never want to reflect arbitrary origins.
    CORS_ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # --- Rate limiting ---
    RATE_LIMIT_PER_MINUTE: int = 60

    # --- External services (placeholders for future integration) ---
    TMDB_API_KEY: str | None = None

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_overridden_in_production(cls, value: str, info: ValidationInfo) -> str:
        """Refuse to boot with the insecure default outside of development/test."""
        environment = info.data.get("ENVIRONMENT", "development")
        if environment == "production" and value == "dev-only-insecure-secret-change-me":
            raise ValueError(
                "SECRET_KEY must be set via environment variable in production. "
                "Refusing to start with the insecure development default."
            )
        return value


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    Cached so every module that needs config imports this function instead of
    re-parsing the environment, while still being overridable in tests via
    `get_settings.cache_clear()` + monkeypatched env vars.
    """
    return Settings()
