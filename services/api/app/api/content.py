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
from app.domain.proposal import generate_proposal
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


class ProposalRequest(BaseModel):
    project_description: str = Field(min_length=10, max_length=10000)
    platform: str = Field(default="upwork", max_length=50)
    tone: str = Field(default="professional")


@router.post("/proposal")
async def proposal(
    body: ProposalRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    persona = await _persona(session, user)
    result = await generate_proposal(
        session, persona, project_description=body.project_description,
        platform=body.platform, tone=body.tone,
    )
    gen_id = await _save(
        session, persona, type_="proposal", title=f"{body.platform} proposal",
        input_={"platform": body.platform}, output=result,
    )
    return {"id": str(gen_id), **result}


class MeetingPrepRequest(BaseModel):
    context: str = Field(min_length=5, max_length=5000,
                         description="Who you're meeting, their company/role, and what it's about")
    focus: str = Field(default="general", max_length=100)


@router.post("/meeting-prep")
async def meeting_prep(
    body: MeetingPrepRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Generate talking points and preparation notes for a meeting."""
    from app.ai.llm import get_llm
    from app.ai.llm.base import Message
    from app.ai.rag.retrieval import build_context_block, retrieve
    from app.core.config import settings

    persona = await _persona(session, user)
    ctx = await retrieve(session, persona, body.context)
    context_block = build_context_block(ctx)
    name = persona.full_name or "the user"

    system = (
        f"You are preparing {name} for a meeting. Based on their professional background below, "
        "generate:\n1) A brief intro they could use (1 sentence)\n"
        "2) 3-5 talking points connecting their experience to the meeting context\n"
        "3) 2-3 questions they could ask\n"
        "Ground everything in actual facts. Do NOT invent experience. Return as structured text "
        "with clear headings.\n\n"
        f"Background:\n{context_block}"
    )
    messages: list[Message] = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Meeting context: {body.context}\nFocus: {body.focus}"},
    ]
    llm = get_llm()
    result = await llm.complete(
        messages, model=settings.llm_model_strong, max_tokens=1000,
        temperature=0.4, purpose="meeting_prep",
    )
    output = {"content": result.text.strip(), "focus": body.focus}
    gen_id = await _save(
        session, persona, type_="meeting_prep", title=body.context[:80],
        input_=body.model_dump(), output=output,
    )
    return {"id": str(gen_id), **output}
