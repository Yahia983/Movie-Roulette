"""Alembic migration environment.

Wired to import `Base.metadata` from the app itself (rather than duplicating
table definitions) so `alembic revision --autogenerate` always reflects the
actual current ORM models, and to `app.core.config.Settings` so the migration
target database is always the same one the app connects to.
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make the `app` package importable when Alembic is invoked from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Import all model modules so they register on Base.metadata before
# autogenerate compares it against the database.
import app.models  # noqa: E402,F401
from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

settings = get_settings()
# Alembic uses the sync driver (psycopg2) since its migration runner is
# synchronous; the app itself uses the async driver at runtime.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL_SYNC)


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection, emitting raw SQL."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
