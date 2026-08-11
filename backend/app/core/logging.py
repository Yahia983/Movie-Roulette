"""Application-wide logging configuration.

Why this exists: default Python logging is unconfigured (WARNING-only, no
formatting) which is unusable in production. We configure it once at startup
so every module can just do `logging.getLogger(__name__)` and get consistent,
structured, timestamped output that's easy to ship to a log aggregator later.
"""

import logging
import sys

from app.core.config import get_settings

settings = get_settings()


def configure_logging() -> None:
    """Configure the root logger. Call once, at application startup."""
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    # Avoid duplicate handlers if configure_logging() is ever called twice
    # (e.g. under a test runner that reimports the app module).
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Quiet down noisy third-party loggers unless we're actively debugging them.
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.DB_ECHO else logging.WARNING
    )
