"""Blog connector endpoints: connect a feed, re-sync."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import get_session
from app.core.errors import AppError, NotFoundError
from app.domain.persona import get_or_create_persona
from app.models.ingestion import Job, Source
from app.models.user import User
from app.schemas.ingestion import JobOut, SourceOut

router = APIRouter(prefix="/sources/blog", tags=["blog"])

PROVIDERS = {"medium", "hashnode", "devto", "rss"}


class BlogConnectRequest(BaseModel):
    provider: str = Field(default="medium")
    handle: str = Field(min_length=1, max_length=500)


class BlogConnectResponse(BaseModel):
    source: SourceOut
    job: JobOut


@router.post("/connect", response_model=BlogConnectResponse, status_code=201)
async def blog_connect(
    body: BlogConnectRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BlogConnectResponse:
    if body.provider not in PROVIDERS:
        raise AppError(
            f"Unknown provider. Choose one of: {', '.join(sorted(PROVIDERS))}",
            code="bad_provider",
        )
    persona = await get_or_create_persona(session, user.id)
    title = f"{body.provider.title()}: {body.handle}"
    source = Source(
        persona_id=persona.id, type="blog", provider=body.provider, title=title,
        status="processing", stats={"provider": body.provider, "handle": body.handle},
    )
    session.add(source)
    await session.flush()

    job = Job(persona_id=persona.id, source_id=source.id, type="sync_blog", status="queued")
    session.add(job)
    await session.flush()
    await _dispatch(job.id)

    return BlogConnectResponse(
        source=SourceOut.model_validate(source), job=JobOut.model_validate(job)
    )


@router.post("/{source_id}/sync", response_model=JobOut, status_code=201)
async def blog_sync(
    source_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> JobOut:
    persona = await get_or_create_persona(session, user.id)
    source = await session.get(Source, source_id)
    if source is None or source.persona_id != persona.id or source.type != "blog":
        raise NotFoundError("Blog source not found")
    source.status = "processing"
    job = Job(persona_id=persona.id, source_id=source.id, type="sync_blog", status="queued")
    session.add(job)
    await session.flush()
    await _dispatch(job.id)
    return JobOut.model_validate(job)


async def _dispatch(job_id) -> None:  # type: ignore[no-untyped-def]
    if settings.environment.lower() == "test":
        return
    from app.workers.tasks import sync_blog_task

    sync_blog_task.delay(str(job_id))
