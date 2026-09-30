"""baseline: postgres extensions

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-01

Makes the required Postgres extensions part of the migration history so the
schema is reproducible without relying on the docker-entrypoint init script.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')


def downgrade() -> None:
    # Extensions are left in place on downgrade; dropping them could affect
    # other objects. Intentionally a no-op.
    pass
