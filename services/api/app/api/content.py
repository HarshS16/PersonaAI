"""Content & communication endpoints: posts, cover letters, application answers."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_session
from app.domain import content as svc
from app.domain.persona import get_or_create_persona
from app.models.generation import Generation
from app.models.persona import Persona
from app.models.user import User

router = APIRouter(prefix="/content", tags=["content"])


class ContentRequest(BaseModel):
    content_type: str = Field(default="linkedin_post")
    topic: str = Field(min_length=1, max_length=2000)
    tone: str = Field(default="professional")


class CoverLetterRequest(BaseModel):
    job_description: str = Field(min_length=10, max_length=20000)
    company: str | None = Field(default=None, max_length=200)
    tone: str = Field(default="professional")


class ApplicationAnswerRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    job_description: str | None = Field(default=None, max_length=20000)


async def _persona(session: AsyncSession, user: User) -> Persona:
    return await get_or_create_persona(session, user.id)


async def _save(
    session: AsyncSession, persona: Persona, *, type_: str, title: str | None,
    input_: dict[str, Any], output: dict[str, Any],
) -> uuid.UUID:
    gen = Generation(persona_id=persona.id, type=type_, title=title, input=input_, output=output)
    session.add(gen)
    await session.flush()
    return gen.id


@router.post("/generate")
async def generate(
    body: ContentRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    persona = await _persona(session, user)
    result = await svc.generate_content(
        session, persona, content_type=body.content_type, topic=body.topic, tone=body.tone
    )
    gen_id = await _save(
        session, persona, type_=f"content:{body.content_type}", title=body.topic[:80],
        input_=body.model_dump(), output=result,
    )
    return {"id": str(gen_id), **result}


@router.post("/cover-letter")
async def cover_letter(
    body: CoverLetterRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    persona = await _persona(session, user)
    result = await svc.generate_cover_letter(
        session, persona, job_description=body.job_description, company=body.company,
        tone=body.tone,
    )
    gen_id = await _save(
        session, persona, type_="cover_letter", title=body.company,
        input_={"company": body.company, "tone": body.tone}, output=result,
    )
    return {"id": str(gen_id), **result}


@router.post("/application-answer")
async def application_answer(
    body: ApplicationAnswerRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    persona = await _persona(session, user)
    result = await svc.generate_application_answer(
        session, persona, question=body.question, job_description=body.job_description
    )
    gen_id = await _save(
        session, persona, type_="application_answer", title=body.question[:80],
        input_={"question": body.question}, output=result,
    )
    return {"id": str(gen_id), **result}
