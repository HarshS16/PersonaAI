"""Shared enums, shared SQLAlchemy column types, and the persona-owned mixin.

Enum columns use ``native_enum=False`` (stored as VARCHAR with a CHECK
constraint) rather than native Postgres ENUM types. This avoids duplicate
``CREATE TYPE`` errors when the same enum is used across many tables, and lets
us add enum values later without an ``ALTER TYPE`` migration.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class Visibility(enum.StrEnum):
    """Who can see a piece of persona data (SRD §34)."""

    private = "private"
    shared = "shared"
    public = "public"


class EvidenceState(enum.StrEnum):
    """How well-supported a fact is (SRD §9)."""

    verified = "verified"  # directly supported by a source
    inferred = "inferred"  # derived from multiple pieces of evidence
    user_confirmed = "user_confirmed"  # explicitly confirmed/entered by the user
    unknown = "unknown"  # no sufficient evidence


class EmploymentType(enum.StrEnum):
    job = "job"
    internship = "internship"
    freelance = "freelance"
    open_source = "open_source"
    volunteer = "volunteer"
    leadership = "leadership"


class PreferenceSource(enum.StrEnum):
    explicit = "explicit"  # user stated it directly
    inferred_pending = "inferred_pending"  # inferred, awaiting confirmation
    confirmed = "confirmed"  # inferred then confirmed by the user


class EntityType(enum.StrEnum):
    """Persona entity kinds, used by evidence and (later) relations."""

    persona = "persona"
    skill = "skill"
    experience = "experience"
    project = "project"
    education = "education"
    achievement = "achievement"
    publication = "publication"
    certification = "certification"
    knowledge_area = "knowledge_area"
    preference = "preference"


def _col_enum(py_enum: type[enum.StrEnum]) -> Enum:
    return Enum(py_enum, native_enum=False, length=32, validate_strings=True)


VisibilityType = _col_enum(Visibility)
EvidenceStateType = _col_enum(EvidenceState)
EmploymentTypeType = _col_enum(EmploymentType)
PreferenceSourceType = _col_enum(PreferenceSource)
EntityTypeType = _col_enum(EntityType)


class PersonaOwnedMixin:
    """Columns shared by every persona-owned fact table.

    Carries ownership, the visibility state (SRD §34), the evidence state and a
    numeric confidence (SRD §9, §48), plus timestamps and soft delete so facts
    can be removed without losing provenance.
    """

    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    visibility: Mapped[Visibility] = mapped_column(
        VisibilityType, default=Visibility.private, nullable=False
    )
    state: Mapped[EvidenceState] = mapped_column(
        EvidenceStateType, default=EvidenceState.user_confirmed, nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = [
    "Visibility",
    "EvidenceState",
    "EmploymentType",
    "PreferenceSource",
    "EntityType",
    "VisibilityType",
    "EvidenceStateType",
    "EmploymentTypeType",
    "PreferenceSourceType",
    "EntityTypeType",
    "PersonaOwnedMixin",
    "Date",
    "String",
    "date",
]
