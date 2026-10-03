"""Persona and persona-fact DTOs."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EmploymentType, EvidenceState, PreferenceSource, Visibility

# ---------------------------------------------------------------------------
# Persona root
# ---------------------------------------------------------------------------


class PersonaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    status: str
    slug: str | None = None
    full_name: str | None
    headline: str | None
    summary: str | None
    location: str | None
    links: dict[str, Any]
    completeness: float
    created_at: datetime
    updated_at: datetime


class PersonaUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=200)
    headline: str | None = Field(default=None, max_length=300)
    summary: str | None = None
    location: str | None = Field(default=None, max_length=200)
    links: dict[str, Any] | None = None
    slug: str | None = Field(default=None, max_length=100, pattern=r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")


# ---------------------------------------------------------------------------
# Shared fact pieces
# ---------------------------------------------------------------------------


class FactMeta(BaseModel):
    """Fields returned for every persona fact."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    visibility: Visibility
    state: EvidenceState
    confidence: float
    created_at: datetime
    updated_at: datetime


class FactPatchMeta(BaseModel):
    visibility: Visibility | None = None


class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    source_id: uuid.UUID | None
    content: str | None
    locator: dict[str, Any]
    state: EvidenceState
    confidence: float
    created_at: datetime


# ---------------------------------------------------------------------------
# Skill
# ---------------------------------------------------------------------------


class SkillCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    category: str | None = Field(default=None, max_length=100)
    visibility: Visibility = Visibility.private


class SkillUpdate(FactPatchMeta):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    category: str | None = Field(default=None, max_length=100)


class SkillOut(FactMeta):
    name: str
    canonical_name: str
    category: str | None
    evidence_count: int


# ---------------------------------------------------------------------------
# Experience
# ---------------------------------------------------------------------------


class ExperienceCreate(BaseModel):
    company: str | None = Field(default=None, max_length=200)
    role: str = Field(min_length=1, max_length=200)
    employment_type: EmploymentType = EmploymentType.job
    location: str | None = Field(default=None, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    description: str | None = None
    highlights: list[str] = Field(default_factory=list)
    visibility: Visibility = Visibility.private


class ExperienceUpdate(FactPatchMeta):
    company: str | None = Field(default=None, max_length=200)
    role: str | None = Field(default=None, max_length=200)
    employment_type: EmploymentType | None = None
    location: str | None = Field(default=None, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool | None = None
    description: str | None = None
    highlights: list[str] | None = None


class ExperienceOut(FactMeta):
    company: str | None
    role: str
    employment_type: EmploymentType
    location: str | None
    start_date: date | None
    end_date: date | None
    is_current: bool
    description: str | None
    highlights: list[str]


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    role: str | None = Field(default=None, max_length=200)
    technologies: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)
    repository_url: str | None = Field(default=None, max_length=500)
    url: str | None = Field(default=None, max_length=500)
    start_date: date | None = None
    end_date: date | None = None
    visibility: Visibility = Visibility.private


class ProjectUpdate(FactPatchMeta):
    name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    role: str | None = Field(default=None, max_length=200)
    technologies: list[str] | None = None
    outcomes: list[str] | None = None
    repository_url: str | None = Field(default=None, max_length=500)
    url: str | None = Field(default=None, max_length=500)
    start_date: date | None = None
    end_date: date | None = None


class ProjectOut(FactMeta):
    name: str
    description: str | None
    role: str | None
    technologies: list[str]
    outcomes: list[str]
    repository_url: str | None
    url: str | None
    start_date: date | None
    end_date: date | None


# ---------------------------------------------------------------------------
# Education
# ---------------------------------------------------------------------------


class EducationCreate(BaseModel):
    institution: str = Field(min_length=1, max_length=200)
    degree: str | None = Field(default=None, max_length=200)
    field_of_study: str | None = Field(default=None, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    grade: str | None = Field(default=None, max_length=100)
    description: str | None = None
    visibility: Visibility = Visibility.private


class EducationUpdate(FactPatchMeta):
    institution: str | None = Field(default=None, max_length=200)
    degree: str | None = Field(default=None, max_length=200)
    field_of_study: str | None = Field(default=None, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    grade: str | None = Field(default=None, max_length=100)
    description: str | None = None


class EducationOut(FactMeta):
    institution: str
    degree: str | None
    field_of_study: str | None
    start_date: date | None
    end_date: date | None
    grade: str | None
    description: str | None


# ---------------------------------------------------------------------------
# Achievement
# ---------------------------------------------------------------------------


class AchievementCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    date_awarded: date | None = None
    issuer: str | None = Field(default=None, max_length=200)
    visibility: Visibility = Visibility.private


class AchievementUpdate(FactPatchMeta):
    title: str | None = Field(default=None, max_length=300)
    description: str | None = None
    date_awarded: date | None = None
    issuer: str | None = Field(default=None, max_length=200)


class AchievementOut(FactMeta):
    title: str
    description: str | None
    date_awarded: date | None
    issuer: str | None


# ---------------------------------------------------------------------------
# Publication
# ---------------------------------------------------------------------------


class PublicationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=400)
    venue: str | None = Field(default=None, max_length=300)
    year: int | None = None
    url: str | None = Field(default=None, max_length=500)
    authors: list[str] = Field(default_factory=list)
    description: str | None = None
    visibility: Visibility = Visibility.private


class PublicationUpdate(FactPatchMeta):
    title: str | None = Field(default=None, max_length=400)
    venue: str | None = Field(default=None, max_length=300)
    year: int | None = None
    url: str | None = Field(default=None, max_length=500)
    authors: list[str] | None = None
    description: str | None = None


class PublicationOut(FactMeta):
    title: str
    venue: str | None
    year: int | None
    url: str | None
    authors: list[str]
    description: str | None


# ---------------------------------------------------------------------------
# Certification
# ---------------------------------------------------------------------------


class CertificationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    issuer: str | None = Field(default=None, max_length=200)
    issue_date: date | None = None
    expiry_date: date | None = None
    credential_id: str | None = Field(default=None, max_length=200)
    url: str | None = Field(default=None, max_length=500)
    visibility: Visibility = Visibility.private


class CertificationUpdate(FactPatchMeta):
    name: str | None = Field(default=None, max_length=300)
    issuer: str | None = Field(default=None, max_length=200)
    issue_date: date | None = None
    expiry_date: date | None = None
    credential_id: str | None = Field(default=None, max_length=200)
    url: str | None = Field(default=None, max_length=500)


class CertificationOut(FactMeta):
    name: str
    issuer: str | None
    issue_date: date | None
    expiry_date: date | None
    credential_id: str | None
    url: str | None


# ---------------------------------------------------------------------------
# Preference
# ---------------------------------------------------------------------------


class PreferenceCreate(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1)
    source: PreferenceSource = PreferenceSource.explicit
    visibility: Visibility = Visibility.private


class PreferenceUpdate(FactPatchMeta):
    key: str | None = Field(default=None, max_length=100)
    value: str | None = None
    source: PreferenceSource | None = None


class PreferenceOut(FactMeta):
    key: str
    value: str
    source: PreferenceSource


# ---------------------------------------------------------------------------
# Knowledge area
# ---------------------------------------------------------------------------


class KnowledgeAreaCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    parent_id: uuid.UUID | None = None
    visibility: Visibility = Visibility.private


class KnowledgeAreaUpdate(FactPatchMeta):
    name: str | None = Field(default=None, max_length=150)
    parent_id: uuid.UUID | None = None


class KnowledgeAreaOut(FactMeta):
    name: str
    parent_id: uuid.UUID | None


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------


class PersonaVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    reason: str | None
    created_at: datetime
