"""Public persona read and "Ask <Name> AI" (SRD §34, §57).

No authentication. Private and shared data is never returned. The slug-based
lookup gives each persona a custom public URL.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import AppError, NotFoundError
from app.core.ratelimit import limiter
from app.domain.public_chat import public_ask
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


async def _resolve_persona(session: AsyncSession, identifier: str) -> Persona:
    """Look up by UUID or slug."""
    try:
        pid = uuid.UUID(identifier)
        persona = await session.get(Persona, pid)
    except ValueError:
        # Slug lookup
        result = await session.execute(
            select(Persona).where(Persona.slug == identifier.lower())
        )
        persona = result.scalar_one_or_none()
    if persona is None:
        raise NotFoundError("Persona not found")
    return persona


def _serialize_persona(persona: Persona, skills: list, projects: list,
                       experiences: list, education: list,
                       achievements: list, publications: list) -> dict[str, Any]:
    return {
        "id": str(persona.id),
        "slug": persona.slug,
        "name": persona.full_name,
        "headline": persona.headline,
        "summary": persona.summary,
        "links": persona.links,
        "skills": [{"name": s.name, "category": s.category} for s in skills],
        "projects": [
            {"name": p.name, "description": p.description, "technologies": p.technologies,
             "url": p.repository_url or p.url}
            for p in projects
        ],
        "experience": [
            {"role": e.role, "company": e.company, "description": e.description,
             "start_date": e.start_date.isoformat() if e.start_date else None,
             "end_date": e.end_date.isoformat() if e.end_date else None}
            for e in experiences
        ],
        "education": [
            {"institution": ed.institution, "degree": ed.degree,
             "field_of_study": ed.field_of_study}
            for ed in education
        ],
        "achievements": [{"title": a.title, "description": a.description} for a in achievements],
        "publications": [
            {"title": pb.title, "venue": pb.venue, "year": pb.year, "url": pb.url}
            for pb in publications
        ],
    }


@router.get("/personas/{identifier}")
async def public_persona(
    identifier: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    persona = await _resolve_persona(session, identifier)
    return _serialize_persona(
        persona,
        await _public(session, Skill, persona.id),
        await _public(session, Project, persona.id),
        await _public(session, Experience, persona.id),
        await _public(session, Education, persona.id),
        await _public(session, Achievement, persona.id),
        await _public(session, Publication, persona.id),
    )


class PublicAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)


@router.post("/personas/{identifier}/ask")
@limiter.limit("20/hour")
async def public_ask_endpoint(
    identifier: str,
    body: PublicAskRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    persona = await _resolve_persona(session, identifier)
    return await public_ask(session, persona, body.question)
