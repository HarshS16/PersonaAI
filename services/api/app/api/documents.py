"""Document upload + ingestion kickoff."""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import get_session
from app.core.errors import AppError
from app.core.ratelimit import limiter
from app.core.storage import get_storage
from app.domain.persona import get_or_create_persona
from app.ingestion.extract_text import detect_kind, extract_text
from app.models.ingestion import Document, Job, Source
from app.models.user import User
from app.schemas.ingestion import JobOut, SourceOut, UploadResponse

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/upload", response_model=UploadResponse, status_code=201)
@limiter.limit("30/hour")
async def upload_document(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UploadResponse:
    filename = file.filename or "upload"
    detect_kind(filename, file.content_type)  # validates type (raises if unsupported)

    data = await file.read()
    if not data:
        raise AppError("Empty file", code="empty_file")
    if len(data) > MAX_BYTES:
        raise AppError("File too large (max 10MB)", code="file_too_large", status_code=413)

    text = extract_text(data, filename, file.content_type)
    if not text.strip():
        raise AppError("Could not extract any text from the document", code="no_text")

    persona = await get_or_create_persona(session, user.id)
    content_hash = hashlib.sha256(data).hexdigest()

    # Dedupe: same bytes already ingested for this persona.
    existing = await session.execute(
        select(Document).where(
            Document.persona_id == persona.id, Document.content_hash == content_hash
        )
    )
    dup = existing.scalar_one_or_none()
    if dup is not None:
        src = await session.get(Source, dup.source_id)
        job_result = await session.execute(
            select(Job)
            .where(Job.source_id == dup.source_id)
            .order_by(Job.created_at.desc())
            .limit(1)
        )
        job = job_result.scalar_one()
        assert src is not None
        return UploadResponse(
            source=SourceOut.model_validate(src),
            job=JobOut.model_validate(job),
            duplicate=True,
        )

    storage = get_storage()
    stored_path = storage.save(data, key_prefix=str(persona.id), filename=filename)

    source = Source(
        persona_id=persona.id,
        type="resume",
        provider="upload",
        title=filename,
        status="processing",
        stats={},
    )
    session.add(source)
    await session.flush()

    document = Document(
        source_id=source.id,
        persona_id=persona.id,
        title=filename,
        mime=file.content_type,
        content=text,
        content_hash=content_hash,
        doc_metadata={"stored_path": stored_path, "bytes": len(data)},
    )
    session.add(document)

    job = Job(persona_id=persona.id, source_id=source.id, type="ingest_document", status="queued")
    session.add(job)
    await session.flush()

    # Enqueue (worker) unless configured to run inline (handy for dev/tests).
    await _dispatch(job.id)

    return UploadResponse(
        source=SourceOut.model_validate(source),
        job=JobOut.model_validate(job),
        duplicate=False,
    )


async def _dispatch(job_id) -> None:  # type: ignore[no-untyped-def]
    if settings.environment.lower() == "test":
        return  # tests invoke the pipeline explicitly
    from app.workers.tasks import ingest_document_task

    ingest_document_task.delay(str(job_id))
