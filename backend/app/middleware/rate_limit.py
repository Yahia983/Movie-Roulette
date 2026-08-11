"""Fixed-window rate limiting middleware, backed by Redis.

Why Redis-backed rather than in-memory: an in-process counter only limits per
worker process, so with N uvicorn workers a client effectively gets N times
the intended limit, and the limit resets on every deploy. Redis gives one
shared counter across all workers and instances, which is what "60 requests
per minute" actually needs to mean.
"""

import logging
import time

from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.cache import get_redis
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Applies a per-client-IP fixed-window rate limit to all requests.

    Health check paths are exempt so orchestrator probes never get throttled.
    """

    EXEMPT_PATHS = {"/health", "/health/ready", "/docs", "/openapi.json"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        window = int(time.time() // 60)
        key = f"ratelimit:{client_ip}:{window}"

        try:
            redis = get_redis()
            current = await redis.incr(key)
            if current == 1:
                # Only set expiry on the first hit in this window, to avoid
                # resetting the TTL on every request and never expiring.
                await redis.expire(key, 60)

            if current > settings.RATE_LIMIT_PER_MINUTE:
                return Response(
                    content='{"detail": "Rate limit exceeded. Please slow down."}',
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    media_type="application/json",
                )
        except Exception:
            # If Redis is unreachable, fail OPEN rather than taking the whole
            # API down over a non-critical protective feature.
            logger.exception("Rate limiter could not reach Redis; allowing request")

        return await call_next(request)
