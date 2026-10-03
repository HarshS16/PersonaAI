"""Calendar source sync: parse ICS data and merge into the persona.

Calendar events are embedded as searchable chunks and an LLM extracts
professional topics, meeting types, and implied areas of expertise.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from app.ai.embeddings import get_embedder
from app.ai.extraction import ExtractedSkill, ResumeExtraction
from app.ai.llm import get_llm
from app.ai.llm.base import Message
from app.connectors.calendar_import import CalendarEvent, parse_ics
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.domain.merge import merge_extraction
from app.domain.persona import (
    EVIDENCE_WEIGHTS,
    compute_completeness,
    snapshot_persona,
)
from app.ingestion.chunk import chunk_text
from app.ingestion.pipeline import SessionFactory, _set_progress
from app.models.ingestion import Chunk, Document, Job, Source
from app.models.persona import Persona

log = get_logger("calendar_sync")
_CAL_W = EVIDENCE_WEIGHTS.get("calendar", 0.3)

_SYSTEM_PROMPT = (
    "You are an assistant that analyses a person's calendar events "
    "to infer professional skills and expertise.\n\n"
    "Given the calendar text below, return a JSON object with:\n"
    "- topics: list of professional topics discussed\n"
    "- meeting_types: list of meeting types "
    "(e.g. 1:1, team standup, client call, interview)\n"
    "- skills: list of {name, category, quote} objects "
    "for areas of expertise implied by meeting topics\n\n"
    "Output ONLY the JSON object."
)


def _build_corpus(events: list[CalendarEvent]) -> str:
    """Build a single text corpus from calendar events."""
    parts: list[str] = []
    for ev in events:
        line = ev.summary
        if ev.description:
            line += " - " + ev.description
        parts.append(line)
    return "\n".join(parts)


async def _extract_calendar_skills(
    corpus: str,
) -> list[ExtractedSkill]:
    """Use LLM to extract professional skills from calendar text."""
    import json as _json

    llm = get_llm()
    messages: list[Message] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Calendar events:\n\n"
                + corpus[:16000]
            ),
        },
    ]
    result = await llm.complete(
        messages,
        model=settings.llm_model_strong,
        max_tokens=4000,
    )
    raw = result.text.strip()
    # Strip markdown code fences if present.
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0]
    try:
        data = _json.loads(raw)
    except _json.JSONDecodeError:
        log.warning("calendar_llm_parse_failed", raw=raw[:200])
        return []

    skills: list[ExtractedSkill] = []
    for item in data.get("skills", []):
        if isinstance(item, dict) and item.get("name"):
            skills.append(
                ExtractedSkill(
                    name=item["name"],
                    category=item.get("category"),
                    quote=item.get("quote", item["name"]),
                )
            )
    return skills


async def sync_calendar_job(
    job_id: uuid.UUID,
    session_factory: SessionFactory | None = None,
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
        log.error(
            "calendar_sync_failed",
            job_id=str(job_id),
            error=str(exc),
        )
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


async def _run(
    sf: SessionFactory, job_id: uuid.UUID
) -> dict[str, Any]:
    async with sf() as s:
        job = await s.get(Job, job_id)
        assert job is not None
        source = (
            await s.get(Source, job.source_id)
            if job.source_id
            else None
        )
        assert source is not None
        persona = await s.get(Persona, job.persona_id)
        assert persona is not None

        raw = (source.stats or {}).get("raw_data")
        if not raw:
            raise ValueError(
                "No raw data attached to calendar source"
            )

        # -- parse -------------------------------------------------
        await _set_progress(
            sf, job_id, step="parsing", progress=0.2
        )
        events = parse_ics(bytes.fromhex(raw))

        # -- embed -------------------------------------------------
        await _set_progress(
            sf, job_id, step="embedding", progress=0.4
        )
        corpus = _build_corpus(events)
        embedder = get_embedder()
        chunks_for_merge: list[tuple[uuid.UUID, str]] = []

        doc = Document(
            source_id=source.id,
            persona_id=persona.id,
            title="Calendar events",
            mime="text/plain",
            content=corpus,
            content_hash=hashlib.sha256(
                corpus.encode()
            ).hexdigest(),
            doc_metadata={"event_count": len(events)},
        )
        s.add(doc)
        await s.flush()

        text_chunks = chunk_text(corpus)
        vectors = await embedder.embed(
            [c.text for c in text_chunks]
        )
        for c, vec in zip(text_chunks, vectors, strict=True):
            ch = Chunk(
                document_id=doc.id,
                persona_id=persona.id,
                ordinal=c.ordinal,
                text=c.text,
                embedding=vec,
                chunk_metadata={"source": "calendar"},
            )
            s.add(ch)
            await s.flush()
            chunks_for_merge.append((ch.id, ch.text))

        # -- LLM extraction ----------------------------------------
        await _set_progress(
            sf, job_id, step="extracting", progress=0.6
        )
        skills = await _extract_calendar_skills(corpus)
        extraction = ResumeExtraction(skills=skills)

        # -- merge -------------------------------------------------
        await snapshot_persona(
            s, persona, reason="Before calendar import"
        )
        await _set_progress(
            sf, job_id, step="merging", progress=0.8
        )
        summary = await merge_extraction(
            s,
            persona,
            extraction,
            source_id=source.id,
            chunks=chunks_for_merge,
            source_label="calendar",
            evidence_weight=_CAL_W,
        )

        await compute_completeness(s, persona)
        source.status = "synced"
        source.last_synced = datetime.now(UTC)
        stats = dict(source.stats or {})
        stats.pop("raw_data", None)
        stats["events"] = len(events)
        stats["merged"] = summary.to_dict()["created"]
        source.stats = stats
        await s.commit()
        return summary.to_dict()
