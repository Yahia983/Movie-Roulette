"""Liveness / readiness endpoints.

Why two endpoints instead of one: an orchestrator (Docker, k8s, a load
balancer) needs to distinguish "the process is alive" from "the process can
actually serve traffic." `/health` answers the former instantly with no
dependencies; `/health/ready` answers the latter by actually touching the
database and cache, so a container isn't routed traffic before its
dependencies are reachable.
"""

import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def liveness() -> dict[str, str]:
    """Cheap liveness probe: if this responds, the process is up."""
    return {"status": "ok"}


@router.get("/health/ready", status_code=status.HTTP_200_OK)
async def readiness(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Readiness probe: confirms the app can actually reach its dependencies."""
    checks = {"database": "unknown", "redis": "unknown"}

    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        logger.exception("Database readiness check failed")
        checks["database"] = "unreachable"

    try:
        redis = get_redis()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception:
        logger.exception("Redis readiness check failed")
        checks["redis"] = "unreachable"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, **checks}
