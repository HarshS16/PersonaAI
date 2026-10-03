"""Agentic job search: persisted search tasks, evaluated leads, and
approval-gated application generation (SRD §58)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class JobSearchTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "job_search_tasks"

    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    criteria: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False,
    )
    # pending | searching | evaluated | completed
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False,
    )
    results_count: Mapped[int] = mapped_column(default=0, nullable=False)


class JobLead(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "job_leads"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_search_tasks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    company: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
    )
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
    )
    source_board: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
    )

    # AI evaluation
    fit_score: Mapped[float] = mapped_column(default=0.0, nullable=False)
    fit_explanation: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    matched_skills: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False,
    )
    missing_skills: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False,
    )

    # Approval gate: pending | approved | rejected | applied
    approval_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False,
    )
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )
