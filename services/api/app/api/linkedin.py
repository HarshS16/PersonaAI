"""LinkedIn data-export upload endpoint."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import get_session
from app.core.errors import AppError
from app.core.ratelimit import limiter
from app.domain.persona import get_or_create_persona
from app.models.ingestion import Job, Source
from app.models.user import User
from app.schemas.ingestion import JobOut, SourceOut, UploadResponse

router = APIRouter(prefix="/sources/linkedin", tags=["linkedin"])

MAX_BYTES = 20 * 1024 * 1024  # 20 MB


@router.post("/upload", response_model=UploadResponse, status_code=201)
@limiter.limit("10/hour")
async def linkedin_upload(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UploadResponse:
    filename = file.filename or "linkedin_export.zip"
    if not filename.lower().endswith(".zip"):
        raise AppError("Please upload the LinkedIn data-export ZIP file", code="bad_file")

    data = await file.read()
    if not data:
        raise AppError("Empty file", code="empty_file")
    if len(data) > MAX_BYTES:
        raise AppError("File too large (max 20MB)", code="file_too_large", status_code=413)

    persona = await get_or_create_persona(session, user.id)

    source = Source(
        persona_id=persona.id, type="linkedin", provider="data_export",
        title=f"LinkedIn export: {filename}",
        status="processing",
        stats={"raw_data": data.hex(), "filename": filename},
    )
    session.add(source)
    await session.flush()

    job = Job(persona_id=persona.id, source_id=source.id, type="sync_linkedin", status="queued")
    session.add(job)
    await session.flush()
    await _dispatch(job.id)

    return UploadResponse(
        source=SourceOut.model_validate(source),
        job=JobOut.model_validate(job),
        duplicate=False,
    )


async def _dispatch(job_id: uuid.UUID) -> None:
    if settings.environment.lower() == "test":
        return
    from app.workers.tasks import sync_linkedin_task

    sync_linkedin_task.delay(str(job_id))
