"""Career endpoints: JD analysis, resume generation, interview preparation."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_session
from app.core.errors import AppError
from app.domain import career as svc
from app.domain.persona import get_or_create_persona
from app.models.generation import Generation
from app.models.persona import Persona
from app.models.user import User

router = APIRouter(tags=["career"])


class JDRequest(BaseModel):
    job_description: str = Field(min_length=10, max_length=20000)


class ResumeRequest(BaseModel):
    job_description: str = Field(min_length=10, max_length=20000)
    target_role: str | None = Field(default=None, max_length=200)
    format: str = Field(default="one_page")


class InterviewRequest(BaseModel):
    mode: str = Field(default="technical")
    job_description: str | None = Field(default=None, max_length=20000)


async def _persona(session: AsyncSession, user: User) -> Persona:
    return await get_or_create_persona(session, user.id)


async def _save(
    session: AsyncSession, persona: Persona, *, type_: str, title: str | None,
    input_: dict[str, Any], output: dict[str, Any],
) -> uuid.UUID:
    gen = Generation(
        persona_id=persona.id, type=type_, title=title, input=input_, output=output
    )
    session.add(gen)
    await session.flush()
    return gen.id


@router.post("/jd/analyze")
async def jd_analyze(
    body: JDRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    persona = await _persona(session, user)
    analysis = await svc.analyze_jd(body.job_description)
    matches = await svc.match_jd(session, persona, analysis)
    gap = svc.summarize_gap(matches)
    output = {
        "analysis": analysis.model_dump(),
        "matches": [
            {
                "requirement": m.requirement,
                "kind": m.kind,
                "status": m.status,
                "evidence": m.evidence,
            }
            for m in matches
        ],
        "gap": gap,
    }
    gen_id = await _save(
        session, persona, type_="jd_analysis", title=analysis.title,
        input_={"job_description": body.job_description}, output=output,
    )
    return {"id": str(gen_id), **output}


@router.post("/resume/generate")
async def resume_generate(
    body: ResumeRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    persona = await _persona(session, user)
    result = await svc.generate_resume(
        session, persona, body.job_description, target_role=body.target_role
    )
    gen_id = await _save(
        session, persona, type_="resume",
        title=body.target_role or result["resume"].get("headline"),
        input_={"job_description": body.job_description, "target_role": body.target_role},
        output=result,
    )
    return {"id": str(gen_id), **result}


@router.post("/interview/start")
async def interview_start(
    body: InterviewRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if body.mode not in svc.INTERVIEW_MODES:
        raise AppError(
            f"Unknown mode. Choose one of: {', '.join(sorted(svc.INTERVIEW_MODES))}",
            code="bad_mode",
        )
    persona = await _persona(session, user)
    questions = await svc.generate_interview(
        session, persona, mode=body.mode, jd_text=body.job_description
    )
    output = {"mode": body.mode, "questions": questions}
    gen_id = await _save(
        session, persona, type_="interview", title=f"{body.mode} interview",
        input_={"mode": body.mode, "has_jd": bool(body.job_description)}, output=output,
    )
    return {"id": str(gen_id), **output}


@router.get("/generations")
async def list_generations(
    type: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    persona = await _persona(session, user)
    stmt = select(Generation).where(Generation.persona_id == persona.id)
    if type:
        stmt = stmt.where(Generation.type == type)
    stmt = stmt.order_by(Generation.created_at.desc()).limit(30)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": str(g.id),
            "type": g.type,
            "title": g.title,
            "created_at": g.created_at.isoformat(),
        }
        for g in rows
    ]


@router.get("/generations/{generation_id}")
async def get_generation(
    generation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    persona = await _persona(session, user)
    gen = await session.get(Generation, generation_id)
    if gen is None or gen.persona_id != persona.id:
        raise AppError("Generation not found", code="not_found", status_code=404)
    return {
        "id": str(gen.id),
        "type": gen.type,
        "title": gen.title,
        "input": gen.input,
        "output": gen.output,
        "created_at": gen.created_at.isoformat(),
    }
