"""add tmdb_id for idempotent catalog sync

Revision ID: e0b31a9ca46b
Revises: 62cf05922c4d
Create Date: 2026-08-07 20:58:27.919096
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e0b31a9ca46b"
down_revision: Union[str, None] = "62cf05922c4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # batch_alter_table is required for SQLite compatibility (SQLite can't
    # ALTER a table to add a constraint directly — batch mode handles this
    # via SQLAlchemy's copy-and-move strategy). It's a transparent no-op
    # wrapper on Postgres, so this works identically in both dev (SQLite)
    # and production (Postgres).
    with op.batch_alter_table("genres") as batch_op:
        batch_op.add_column(sa.Column("tmdb_id", sa.Integer(), nullable=True))
        batch_op.create_unique_constraint(op.f("uq_genres_tmdb_id"), ["tmdb_id"])

    with op.batch_alter_table("people") as batch_op:
        batch_op.add_column(sa.Column("tmdb_id", sa.Integer(), nullable=True))
        batch_op.create_index(op.f("ix_people_tmdb_id"), ["tmdb_id"], unique=True)

    with op.batch_alter_table("titles") as batch_op:
        batch_op.add_column(sa.Column("tmdb_id", sa.Integer(), nullable=True))
        batch_op.create_index(op.f("ix_titles_tmdb_id"), ["tmdb_id"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("titles") as batch_op:
        batch_op.drop_index(op.f("ix_titles_tmdb_id"))
        batch_op.drop_column("tmdb_id")

    with op.batch_alter_table("people") as batch_op:
        batch_op.drop_index(op.f("ix_people_tmdb_id"))
        batch_op.drop_column("tmdb_id")

    with op.batch_alter_table("genres") as batch_op:
        batch_op.drop_constraint(op.f("uq_genres_tmdb_id"), type_="unique")
        batch_op.drop_column("tmdb_id")
