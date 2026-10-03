"""add persona slug

Revision ID: a3b8f1c2d4e5
Revises: 1e7130371c21
Create Date: 2026-10-03 12:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = 'a3b8f1c2d4e5'
down_revision: str | None = '1e7130371c21'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('personas', sa.Column('slug', sa.String(length=100), nullable=True))
    op.create_unique_constraint(op.f('uq_personas_slug'), 'personas', ['slug'])


def downgrade() -> None:
    op.drop_constraint(op.f('uq_personas_slug'), 'personas', type_='unique')
    op.drop_column('personas', 'slug')
