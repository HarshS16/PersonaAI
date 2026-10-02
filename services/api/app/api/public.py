"""Public persona read (SRD §34): exposes ONLY facts marked public.

No authentication. Private and shared data is never returned here, which is the
enforcement point for the platform's visibility model. The interactive
"Ask <Name> AI" public page builds on this in a later phase.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import NotFoundError
from app.models.enums import Visibility
from app.models.facts import Achievement, Education, Experience, Project, Publication, Skill
from app.models.persona import Persona

router = APIRouter(prefix="/public", tags=["public"])


async def _public(session: AsyncSession, model: Any, persona_id: uuid.UUID) -> list[Any]:
    rows = await session.execute(
        select(model).where(
            model.persona_id == persona_id,
            model.deleted_at.is_(None),
            model.visibility == Visibility.public,
        )
    )
    return list(rows.scalars().all())


@router.get("/personas/{persona_id}")
async def public_persona(
    persona_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    persona = await session.get(Persona, persona_id)
    if persona is None:
        raise NotFoundError("Persona not found")

    skills = await _public(session, Skill, persona_id)
    projects = await _public(session, Project, persona_id)
    experiences = await _public(session, Experience, persona_id)
    education = await _public(session, Education, persona_id)
    achievements = await _public(session, Achievement, persona_id)
    publications = await _public(session, Publication, persona_id)

    return {
        "name": persona.full_name,
        "headline": persona.headline,
        "summary": persona.summary,
        "skills": [{"name": s.name, "category": s.category} for s in skills],
        "projects": [
            {"name": p.name, "description": p.description, "technologies": p.technologies,
             "url": p.repository_url or p.url}
            for p in projects
        ],
        "experience": [
            {"role": e.role, "company": e.company, "description": e.description}
            for e in experiences
        ],
        "education": [
            {"institution": ed.institution, "degree": ed.degree,
             "field_of_study": ed.field_of_study}
            for ed in education
        ],
        "achievements": [{"title": a.title, "description": a.description} for a in achievements],
        "publications": [
            {"title": pb.title, "venue": pb.venue, "year": pb.year} for pb in publications
        ],
    }
