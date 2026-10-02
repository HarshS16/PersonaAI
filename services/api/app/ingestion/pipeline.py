"""Ingestion orchestration.

The persona-mutating work (snapshot -> chunk -> embed -> extract -> merge)
runs in a single transaction that commits only on success, so a failure leaves
the persona untouched (SRD §60). Job progress is written through a separate
short-lived session so the UI can watch it live.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import get_embedder
from app.ai.llm import get_llm
from app.ai.usage import record_ai_call
from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.domain.merge import merge_extraction
from app.domain.persona import compute_completeness, snapshot_persona
from app.ingestion.chunk import chunk_text
from app.ingestion.extract_facts import extract_resume
from app.models.ingestion import Chunk, Document, Job, Source
from app.models.persona import Persona

log = get_logger("ingestion")

# A session factory so the Celery worker can pass a fresh, loop-local engine
# per task (its default global engine cannot span the per-task event loops).
SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


async def _set_progress(
    sf: SessionFactory, job_id: uuid.UUID, *, step: str, progress: float
) -> None:
    async with sf() as s:
        job = await s.get(Job, job_id)
        if job:
            job.step = step
            job.progress = progress
            await s.commit()


async def ingest_job(
    job_id: uuid.UUID, session_factory: SessionFactory | None = None
) -> dict[str, Any]:
    """Run a document-ingestion job. Returns the merge summary."""
    sf: SessionFactory = session_factory or SessionLocal
    async with sf() as s:
        job = await s.get(Job, job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")
        job.status = "running"
        job.attempts += 1
        await s.commit()

    try:
        summary = await _run(sf, job_id)
    except Exception as exc:  # noqa: BLE001 - we record and re-raise for retry
        log.error("ingestion_failed", job_id=str(job_id), error=str(exc))
        async with sf() as s:
            job = await s.get(Job, job_id)
            if job:
                job.status = "failed"
                job.error = str(exc)[:1000]
                if job.source_id:
                    src = await s.get(Source, job.source_id)
                    if src:
                        src.status = "error"
                        src.error = str(exc)[:1000]
                await s.commit()
        raise

    async with sf() as s:
        job = await s.get(Job, job_id)
        if job:
            job.status = "succeeded"
            job.progress = 1.0
            job.step = "done"
            job.result = summary
            await s.commit()
    return summary


async def _run(sf: SessionFactory, job_id: uuid.UUID) -> dict[str, Any]:
    async with sf() as s:
        job = await s.get(Job, job_id)
        assert job is not None
        source = await s.get(Source, job.source_id) if job.source_id else None
        assert source is not None
        persona = await s.get(Persona, job.persona_id)
        assert persona is not None

        doc_result = await s.execute(
            select(Document).where(Document.source_id == source.id).limit(1)
        )
        doc = doc_result.scalar_one_or_none()
        if doc is None:
            raise ValueError("No document attached to source")

        # 1. Chunk
        await _set_progress(sf, job_id, step="chunking", progress=0.15)
        text_chunks = chunk_text(doc.content)

        # 2. Embed + persist chunks
        await _set_progress(sf, job_id, step="embedding", progress=0.35)
        embedder = get_embedder()
        vectors = await embedder.embed([tc.text for tc in text_chunks])
        chunk_rows: list[Chunk] = []
        for tc, vec in zip(text_chunks, vectors, strict=True):
            ch = Chunk(
                document_id=doc.id,
                persona_id=persona.id,
                ordinal=tc.ordinal,
                text=tc.text,
                embedding=vec,
                chunk_metadata={"section": tc.section},
            )
            s.add(ch)
            chunk_rows.append(ch)
        await s.flush()
        chunks_for_merge = [(ch.id, ch.text) for ch in chunk_rows]

        # 3. Snapshot persona before mutating (recoverable, SRD §60)
        await snapshot_persona(s, persona, reason=f"Before ingesting {source.title or 'source'}")

        # 4. Extract facts
        await _set_progress(sf, job_id, step="extracting", progress=0.6)
        extraction, llm_result = await extract_resume(doc.content)
        await record_ai_call(s, llm_result, persona_id=persona.id, provider=get_llm().name)

        # 5. Merge into persona
        await _set_progress(sf, job_id, step="merging", progress=0.85)
        summary = await merge_extraction(
            s, persona, extraction, source_id=source.id, chunks=chunks_for_merge
        )

        # 6. Finalize
        await compute_completeness(s, persona)
        source.status = "synced"
        source.last_synced = datetime.now(UTC)
        source.stats = summary.to_dict()

        await s.commit()
        return summary.to_dict()
