"""PKM (bookmarks & notes) upload endpoints."""

from __future__ import annotations

import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    Request,
    Response,
    UploadFile,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import get_session
from app.core.errors import AppError
from app.core.ratelimit import limiter
from app.domain.persona import get_or_create_persona
from app.models.ingestion import Job, Source
from app.models.user import User
from app.schemas.ingestion import (
    JobOut,
    SourceOut,
    UploadResponse,
)

router = APIRouter(
    prefix="/sources/pkm", tags=["pkm"]
)

MAX_BOOKMARKS_BYTES = 5 * 1024 * 1024   # 5 MB
MAX_NOTES_BYTES = 20 * 1024 * 1024      # 20 MB


@router.post(
    "/bookmarks/upload",
    response_model=UploadResponse,
    status_code=201,
)
@limiter.limit("10/hour")
async def bookmarks_upload(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UploadResponse:
    filename = file.filename or "bookmarks.html"
    if not filename.lower().endswith(".html"):
        raise AppError(
            "Please upload a browser bookmark export "
            "(.html file)",
            code="bad_file",
        )

    data = await file.read()
    if not data:
        raise AppError("Empty file", code="empty_file")
    if len(data) > MAX_BOOKMARKS_BYTES:
        raise AppError(
            "File too large (max 5MB)",
            code="file_too_large",
            status_code=413,
        )

    persona = await get_or_create_persona(
        session, user.id
    )

    source = Source(
        persona_id=persona.id,
        type="pkm",
        provider="bookmarks",
        title=f"Bookmarks: {filename}",
        status="processing",
        stats={
            "raw_data": data.hex(),
            "filename": filename,
            "subtype": "bookmarks",
        },
    )
    session.add(source)
    await session.flush()

    job = Job(
        persona_id=persona.id,
        source_id=source.id,
        type="sync_pkm",
        status="queued",
    )
    session.add(job)
    await session.flush()
    await _dispatch(job.id)

    return UploadResponse(
        source=SourceOut.model_validate(source),
        job=JobOut.model_validate(job),
        duplicate=False,
    )


@router.post(
    "/notes/upload",
    response_model=UploadResponse,
    status_code=201,
)
@limiter.limit("10/hour")
async def notes_upload(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UploadResponse:
    filename = file.filename or "notes.md"
    ext = filename.lower().rsplit(".", 1)[-1]
    if ext not in ("md", "zip"):
        raise AppError(
            "Please upload a .md or .zip file",
            code="bad_file",
        )

    data = await file.read()
    if not data:
        raise AppError("Empty file", code="empty_file")
    if len(data) > MAX_NOTES_BYTES:
        raise AppError(
            "File too large (max 20MB)",
            code="file_too_large",
            status_code=413,
        )

    persona = await get_or_create_persona(
        session, user.id
    )

    source = Source(
        persona_id=persona.id,
        type="pkm",
        provider="notes",
        title=f"Notes: {filename}",
        status="processing",
        stats={
            "raw_data": data.hex(),
            "filename": filename,
            "subtype": "notes",
        },
    )
    session.add(source)
    await session.flush()

    job = Job(
        persona_id=persona.id,
        source_id=source.id,
        type="sync_pkm",
        status="queued",
    )
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
    from app.workers.tasks import sync_pkm_task

    sync_pkm_task.delay(str(job_id))
