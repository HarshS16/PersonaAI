"""LinkedIn data-export sync: parse the ZIP and merge into the persona."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.connectors.linkedin import parse_linkedin_export
from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.domain.merge import merge_extraction
from app.domain.persona import EVIDENCE_WEIGHTS, compute_completeness, snapshot_persona
from app.ingestion.pipeline import SessionFactory, _set_progress
from app.models.ingestion import Job, Source
from app.models.persona import Persona

log = get_logger("linkedin_sync")
_LI_W = EVIDENCE_WEIGHTS.get("linkedin", 0.7)


async def sync_linkedin_job(
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
        log.error("linkedin_sync_failed", job_id=str(job_id), error=str(exc))
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

        raw = (source.stats or {}).get("raw_data")
        if not raw:
            raise ValueError("No raw data attached to linkedin source")

        await _set_progress(sf, job_id, step="parsing", progress=0.3)
        extraction = parse_linkedin_export(bytes.fromhex(raw))

        await snapshot_persona(s, persona, reason="Before LinkedIn import")

        await _set_progress(sf, job_id, step="merging", progress=0.6)
        summary = await merge_extraction(
            s, persona, extraction, source_id=source.id, chunks=[],
            source_label="linkedin", evidence_weight=_LI_W,
        )

        await compute_completeness(s, persona)
        source.status = "synced"
        source.last_synced = datetime.now(UTC)
        stats = dict(source.stats or {})
        stats.pop("raw_data", None)  # Don't persist the raw ZIP hex
        stats["merged"] = summary.to_dict()["created"]
        source.stats = stats
        await s.commit()
        return summary.to_dict()
