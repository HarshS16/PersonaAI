"""Add job_search_tasks and job_leads tables for Phase 4.

Revision ID: b4c9e2f3a5d7
Revises: a3b8f1c2d4e5
Create Date: 2026-10-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "b4c9e2f3a5d7"
down_revision = "a3b8f1c2d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_search_tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "persona_id", UUID(as_uuid=True),
            sa.ForeignKey("personas.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column("criteria", JSONB, server_default="{}", nullable=False),
        sa.Column(
            "status", sa.String(20),
            server_default="pending", nullable=False,
        ),
        sa.Column(
            "results_count", sa.Integer,
            server_default="0", nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )

    op.create_table(
        "job_leads",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id", UUID(as_uuid=True),
            sa.ForeignKey("job_search_tasks.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "persona_id", UUID(as_uuid=True),
            sa.ForeignKey("personas.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("company", sa.String(200), nullable=True),
        sa.Column("url", sa.String(1000), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("source_board", sa.String(50), nullable=True),
        sa.Column(
            "fit_score", sa.Float,
            server_default="0.0", nullable=False,
        ),
        sa.Column("fit_explanation", sa.Text, nullable=True),
        sa.Column("matched_skills", JSONB, server_default="[]", nullable=False),
        sa.Column("missing_skills", JSONB, server_default="[]", nullable=False),
        sa.Column(
            "approval_status", sa.String(20),
            server_default="pending", nullable=False,
        ),
        sa.Column("application_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("job_leads")
    op.drop_table("job_search_tasks")
