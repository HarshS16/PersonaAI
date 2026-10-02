"""Source management: list, inspect, disconnect; jobs; conflicts."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_session
from app.core.errors import NotFoundError
from app.domain.persona import (
    compute_completeness,
    get_or_create_persona,
    recompute_entities,
)
from app.models.evidence import Evidence
from app.models.ingestion import Conflict, Job, Source
from app.models.user import User
from app.schemas.ingestion import ConflictOut, JobOut, ResolveConflictRequest, SourceOut

router = APIRouter(tags=["sources"])


@router.get("/sources", response_model=list[SourceOut])
async def list_sources(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[SourceOut]:
    persona = await get_or_create_persona(session, user.id)
    result = await session.execute(
        select(Source).where(Source.persona_id == persona.id).order_by(Source.created_at.desc())
    )
    return [SourceOut.model_validate(s) for s in result.scalars().all()]


@router.delete("/sources/{source_id}", status_code=204)
async def disconnect_source(
    source_id: uuid.UUID,
    response: Response,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    persona = await get_or_create_persona(session, user.id)
    source = await session.get(Source, source_id)
    if source is None or source.persona_id != persona.id:
        raise NotFoundError("Source not found")

    # Note which facts this source's evidence supports, so we can recompute their
    # confidence after removing it (documents/chunks cascade via FK).
    affected_rows = await session.execute(
        select(Evidence.entity_type, Evidence.entity_id).where(Evidence.source_id == source_id)
    )
    affected = {(et, eid) for et, eid in affected_rows.all()}

    await session.execute(delete(Evidence).where(Evidence.source_id == source_id))
    await session.delete(source)
    await session.flush()

    await recompute_entities(session, affected)
    await compute_completeness(session, persona)
    response.status_code = 204
    return response


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> JobOut:
    persona = await get_or_create_persona(session, user.id)
    job = await session.get(Job, job_id)
    if job is None or job.persona_id != persona.id:
        raise NotFoundError("Job not found")
    return JobOut.model_validate(job)


@router.get("/jobs", response_model=list[JobOut])
async def list_jobs(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[JobOut]:
    persona = await get_or_create_persona(session, user.id)
    result = await session.execute(
        select(Job).where(Job.persona_id == persona.id).order_by(Job.created_at.desc()).limit(20)
    )
    return [JobOut.model_validate(j) for j in result.scalars().all()]


@router.get("/conflicts", response_model=list[ConflictOut])
async def list_conflicts(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ConflictOut]:
    persona = await get_or_create_persona(session, user.id)
    result = await session.execute(
        select(Conflict)
        .where(Conflict.persona_id == persona.id, Conflict.status == "open")
        .order_by(Conflict.created_at.desc())
    )
    return [ConflictOut.model_validate(c) for c in result.scalars().all()]


@router.post("/conflicts/{conflict_id}/resolve", response_model=ConflictOut)
async def resolve_conflict(
    conflict_id: uuid.UUID,
    body: ResolveConflictRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConflictOut:
    persona = await get_or_create_persona(session, user.id)
    conflict = await session.get(Conflict, conflict_id)
    if conflict is None or conflict.persona_id != persona.id:
        raise NotFoundError("Conflict not found")

    # Apply the chosen value to the persona identity field.
    if conflict.field in {"full_name", "headline", "location", "summary"}:
        setattr(persona, conflict.field, body.chosen_value)

    conflict.status = "resolved"
    conflict.resolution = {"chosen_value": body.chosen_value}
    await session.flush()
    return ConflictOut.model_validate(conflict)
