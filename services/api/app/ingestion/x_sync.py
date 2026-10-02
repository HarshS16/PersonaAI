"""X/Twitter archive sync: parse tweets, embed them, update writing style."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from app.ai.embeddings import get_embedder
from app.ai.writing_style import analyze_style
from app.connectors.x_archive import parse_x_archive
from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.domain.persona import compute_completeness
from app.ingestion.blog_sync import _upsert_writing_style
from app.ingestion.chunk import chunk_text
from app.ingestion.pipeline import SessionFactory, _set_progress
from app.models.ingestion import Chunk, Document, Job, Source
from app.models.persona import Persona

log = get_logger("x_sync")


async def sync_x_job(
    job_id: uuid.UUID, session_factory: SessionFactory | None = None
) -> dict[str, Any]:
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
    except Exception as exc:  # noqa: BLE001
        log.error("x_sync_failed", job_id=str(job_id), error=str(exc))
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

        raw_hex = (source.stats or {}).get("raw_data")
        filename = (source.stats or {}).get("filename", "tweets.js")
        if not raw_hex:
            raise ValueError("No raw data attached to X source")

        await _set_progress(sf, job_id, step="parsing", progress=0.2)
        tweets = parse_x_archive(bytes.fromhex(raw_hex), filename)

        await _set_progress(sf, job_id, step="embedding", progress=0.5)
        # Combine tweets into a single document for searchability.
        combined = "\n\n".join(tweets)
        doc = Document(
            source_id=source.id, persona_id=persona.id,
            title="X/Twitter archive", mime="text/plain",
            content=combined,
            content_hash=hashlib.sha256(combined.encode()).hexdigest(),
            doc_metadata={"tweet_count": len(tweets)},
        )
        s.add(doc)
        await s.flush()

        embedder = get_embedder()
        text_chunks = chunk_text(combined)
        vectors = await embedder.embed([c.text for c in text_chunks])
        for c, vec in zip(text_chunks, vectors, strict=True):
            ch = Chunk(
                document_id=doc.id, persona_id=persona.id, ordinal=c.ordinal,
                text=c.text, embedding=vec,
                chunk_metadata={"source": "x_archive"},
            )
            s.add(ch)

        # Writing style from short-form tweets
        await _set_progress(sf, job_id, step="style_analysis", progress=0.8)
        await _upsert_writing_style(s, persona.id, analyze_style(tweets))

        await compute_completeness(s, persona)
        source.status = "synced"
        source.last_synced = datetime.now(UTC)
        stats = dict(source.stats or {})
        stats.pop("raw_data", None)
        stats["tweets"] = len(tweets)
        source.stats = stats
        await s.commit()
        return {"tweets_indexed": len(tweets), "chunks": len(text_chunks)}
