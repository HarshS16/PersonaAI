"""Persona fact tables: skills, experience, projects, education, achievements,
publications (research), and certifications. All inherit PersonaOwnedMixin, so
each carries visibility, evidence state, confidence, and soft delete.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import Date, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.enums import EmploymentType, EmploymentTypeType, PersonaOwnedMixin
from app.models.mixins import UUIDPrimaryKeyMixin


class Skill(PersonaOwnedMixin, UUIDPrimaryKeyMixin, Base):
    __tablename__ = "skills"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    # Normalized form for dedupe/merge (e.g. "ReactJS" -> "react").
    canonical_name: Mapped[str] = mapped_column(String(150), index=True, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Experience(PersonaOwnedMixin, UUIDPrimaryKeyMixin, Base):
    __tablename__ = "experiences"

    company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    role: Mapped[str] = mapped_column(String(200), nullable=False)
    employment_type: Mapped[EmploymentType] = mapped_column(
        EmploymentTypeType, default=EmploymentType.job, nullable=False
    )
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(default=False, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    highlights: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)


class Project(PersonaOwnedMixin, UUIDPrimaryKeyMixin, Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str | None] = mapped_column(String(200), nullable=True)
    technologies: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    outcomes: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    repository_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class Education(PersonaOwnedMixin, UUIDPrimaryKeyMixin, Base):
    __tablename__ = "education"

    institution: Mapped[str] = mapped_column(String(200), nullable=False)
    degree: Mapped[str | None] = mapped_column(String(200), nullable=True)
    field_of_study: Mapped[str | None] = mapped_column(String(200), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    grade: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)


class Achievement(PersonaOwnedMixin, UUIDPrimaryKeyMixin, Base):
    __tablename__ = "achievements"

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    date_awarded: Mapped[date | None] = mapped_column(Date, nullable=True)
    issuer: Mapped[str | None] = mapped_column(String(200), nullable=True)


class Publication(PersonaOwnedMixin, UUIDPrimaryKeyMixin, Base):
    """Research output (SRD §8, §63)."""

    __tablename__ = "publications"

    title: Mapped[str] = mapped_column(String(400), nullable=False)
    venue: Mapped[str | None] = mapped_column(String(300), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    authors: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, nullable=False
    )


class Certification(PersonaOwnedMixin, UUIDPrimaryKeyMixin, Base):
    __tablename__ = "certifications"

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    issuer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    credential_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
