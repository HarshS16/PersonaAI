"""Persona root, version snapshots, writing style, preferences, knowledge areas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import (
    PersonaOwnedMixin,
    PreferenceSource,
    PreferenceSourceType,
)
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Persona(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The root persona for a user (one per user in the MVP)."""

    __tablename__ = "personas"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    slug: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)

    # Identity layer (SRD §8.1)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    headline: Mapped[str | None] = mapped_column(String(300), nullable=True)
    summary: Mapped[str | None] = mapped_column(String, nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    links: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    completeness: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


class PersonaVersion(UUIDPrimaryKeyMixin, Base):
    """Immutable snapshot of a persona for recovery/rollback (SRD §60)."""

    __tablename__ = "persona_versions"

    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WritingStyle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-persona writing-style metrics (SRD §8.6). One row per persona."""

    __tablename__ = "writing_styles"

    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class Preference(PersonaOwnedMixin, UUIDPrimaryKeyMixin, Base):
    """Career/work preferences (SRD §8.7)."""

    __tablename__ = "preferences"

    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[PreferenceSource] = mapped_column(
        PreferenceSourceType, default=PreferenceSource.explicit, nullable=False
    )

    evidence: Mapped[list[Evidence]] = relationship(
        primaryjoin="and_(foreign(Evidence.entity_id) == Preference.id, "
        "Evidence.entity_type == 'preference')",
        viewonly=True,
    )


class KnowledgeArea(PersonaOwnedMixin, UUIDPrimaryKeyMixin, Base):
    """Conceptual knowledge areas as a tree (SRD §8.5)."""

    __tablename__ = "knowledge_areas"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_areas.id", ondelete="SET NULL"), nullable=True
    )


# Imported at end to avoid circular import at module load.
from app.models.evidence import Evidence  # noqa: E402
