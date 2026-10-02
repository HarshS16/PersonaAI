"""Blog source sync: ingest articles from a feed into the persona.

Articles become embedded, searchable documents; skills written about become
low-weight evidence; and the articles feed writing-style analysis so generated
content can match the author's voice.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.ai.embeddings import get_embedder
from app.ai.extraction import ResumeExtraction
from app.ai.writing_style import analyze_style
from app.connectors.blog import get_blog_client
from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.domain.merge import merge_extraction
from app.domain.persona import EVIDENCE_WEIGHTS, compute_completeness, snapshot_persona
from app.ingestion.chunk import chunk_text
from app.ingestion.extract_facts import extract_resume
from app.ingestion.pipeline import SessionFactory, _set_progress
from app.models.ingestion import Chunk, Document, Job, Source
from app.models.persona import Persona, WritingStyle

log = get_logger("blog_sync")
_BLOG_W = EVIDENCE_WEIGHTS["blog"]


async def sync_blog_job(
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
        log.error("blog_sync_failed", job_id=str(job_id), error=str(exc))
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


async def _upsert_writing_style(s: Any, persona_id: uuid.UUID, metrics: dict[str, Any]) -> None:
    if not metrics:
        return
    existing = (
        await s.execute(select(WritingStyle).where(WritingStyle.persona_id == persona_id))
    ).scalar_one_or_none()
    if existing is None:
        s.add(WritingStyle(persona_id=persona_id, metrics=metrics))
    else:
        existing.metrics = metrics


async def _run(sf: SessionFactory, job_id: uuid.UUID) -> dict[str, Any]:
    async with sf() as s:
        job = await s.get(Job, job_id)
        assert job is not None
        source = await s.get(Source, job.source_id) if job.source_id else None
        assert source is not None
        persona = await s.get(Persona, job.persona_id)
        assert persona is not None

        provider = (source.stats or {}).get("provider", "rss")
        handle = (source.stats or {}).get("handle", "")

        await _set_progress(sf, job_id, step="fetching", progress=0.2)
        data = await get_blog_client().fetch(provider=provider, handle=handle)
        if not data.articles:
            raise ValueError("No articles found in the feed")

        await _set_progress(sf, job_id, step="embedding", progress=0.5)
        embedder = get_embedder()
        chunks_for_merge: list[tuple[uuid.UUID, str]] = []
        article_texts: list[str] = []
        for art in data.articles:
            article_texts.append(art.content)
            doc = Document(
                source_id=source.id,
                persona_id=persona.id,
                title=art.title,
                mime="text/plain",
                content=art.content,
                content_hash=hashlib.sha256(f"{art.url}:{art.content}".encode()).hexdigest(),
                doc_metadata={"url": art.url, "published": art.published},
            )
            s.add(doc)
            await s.flush()
            text_chunks = chunk_text(art.content)
            vectors = await embedder.embed([c.text for c in text_chunks])
            for c, vec in zip(text_chunks, vectors, strict=True):
                ch = Chunk(
                    document_id=doc.id, persona_id=persona.id, ordinal=c.ordinal,
                    text=c.text, embedding=vec,
                    chunk_metadata={"article": art.title, "section": c.section},
                )
                s.add(ch)
                await s.flush()
                chunks_for_merge.append((ch.id, ch.text))

        await snapshot_persona(s, persona, reason=f"Before blog sync ({data.handle})")

        # Skills written about become low-weight evidence (ignore resume-shaped
        # experiences/projects the extractor might hallucinate from prose).
        await _set_progress(sf, job_id, step="merging", progress=0.8)
        extraction, _ = await extract_resume("\n\n".join(article_texts)[:16000])
        blog_extraction = ResumeExtraction(skills=extraction.skills)
        summary = await merge_extraction(
            s, persona, blog_extraction, source_id=source.id, chunks=chunks_for_merge,
            source_label="blog", evidence_weight=_BLOG_W,
        )

        # Writing-style analysis.
        await _upsert_writing_style(s, persona.id, analyze_style(article_texts))

        await compute_completeness(s, persona)
        source.status = "synced"
        source.last_synced = datetime.now(UTC)
        stats = dict(source.stats or {})
        stats.update({"articles": len(data.articles), "created": summary.to_dict()["created"]})
        source.stats = stats
        await s.commit()
        return summary.to_dict()
