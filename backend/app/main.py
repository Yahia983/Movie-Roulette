"""MovieRoulette API entrypoint.

Uses the application-factory pattern (`create_app()`) rather than a bare
module-level `app = FastAPI()` so tests can construct isolated app instances
with overridden settings/dependencies, and so startup/shutdown wiring lives
in one obvious place.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.middleware.rate_limit import RateLimitMiddleware

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown hooks.

    Kept minimal for now (just logging); this is where later phases will add
    things like warming a recommendation-model cache or verifying migrations
    are up to date before accepting traffic.
    """
    configure_logging()
    logger.info("Starting %s in %s mode", settings.PROJECT_NAME, settings.ENVIRONMENT)
    yield
    logger.info("Shutting down %s", settings.PROJECT_NAME)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="Never wonder what to watch again.",
        version="0.1.0",
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS: explicit origin allow-list (see core/config.py) since the
    # frontend is a fully decoupled static app served from its own origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(RateLimitMiddleware)

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
