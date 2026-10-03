"""Structured-extraction schemas.

Every extracted item carries a verbatim ``quote`` from the source text. That
quote becomes the fact's evidence, which is how the platform keeps claims
grounded (SRD §9, §49): no quote, no fact.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractedSkill(BaseModel):
    name: str
    category: str | None = None
    quote: str = Field(description="Verbatim text from the document supporting this skill")


class ExtractedExperience(BaseModel):
    role: str
    company: str | None = None
    start_date: str | None = Field(default=None, description="ISO date or year, if present")
    end_date: str | None = None
    description: str | None = None
    quote: str


class ExtractedProject(BaseModel):
    name: str
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)
    quote: str


class ExtractedEducation(BaseModel):
    institution: str
    degree: str | None = None
    field_of_study: str | None = None
    quote: str


class ExtractedAchievement(BaseModel):
    title: str
    quote: str


class ExtractedPublication(BaseModel):
    title: str
    venue: str | None = None
    year: int | None = None
    url: str | None = None
    quote: str


class JDAnalysis(BaseModel):
    """Structured requirements extracted from a job description (SRD §26)."""

    title: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    experience_years: int | None = None
    education: str | None = None
    domain: str | None = None


class ResumeExtraction(BaseModel):
    """Everything extractable from a resume-like document."""

    full_name: str | None = None
    headline: str | None = Field(default=None, description="Professional title / headline")
    location: str | None = None
    summary: str | None = None
    skills: list[ExtractedSkill] = Field(default_factory=list)
    experiences: list[ExtractedExperience] = Field(default_factory=list)
    projects: list[ExtractedProject] = Field(default_factory=list)
    education: list[ExtractedEducation] = Field(default_factory=list)
    achievements: list[ExtractedAchievement] = Field(default_factory=list)
    publications: list[ExtractedPublication] = Field(default_factory=list)
