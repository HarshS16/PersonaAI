"""Email import sync: parse uploaded MBOX/.eml and merge into the persona."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from app.ai.embeddings import get_embedder
from app.ai.extraction import ExtractedSkill, ResumeExtraction
from app.ai.llm import get_llm
from app.ai.llm.base import Message
from app.connectors.email_import import EmailMessage, parse_eml, parse_mbox
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

log = get_logger("email_sync")
_EMAIL_W = EVIDENCE_WEIGHTS.get("email", 0.4)


async def sync_email_job(
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
        log.error("email_sync_failed", job_id=str(job_id), error=str(exc))
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


def _parse_emails(raw_hex: str, filename: str) -> list[EmailMessage]:
    """Decode raw data and parse into EmailMessage list."""
    data = bytes.fromhex(raw_hex)
    lower = filename.lower()
    if lower.endswith(".eml"):
        return [parse_eml(data)]
    if lower.endswith(".mbox"):
        return parse_mbox(data)
    if lower.endswith(".zip"):
        import io
        import zipfile

        emails: list[EmailMessage] = []
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as exc:
            raise ValueError("Not a valid ZIP file") from exc
        for name in zf.namelist():
            if len(emails) >= 500:
                break
            nl = name.lower()
            if nl.endswith(".eml"):
                eml_data = zf.read(name)
                emails.append(parse_eml(eml_data))
            elif nl.endswith(".mbox"):
                mbox_data = zf.read(name)
                emails.extend(parse_mbox(mbox_data))
        return emails[:500]
    raise ValueError(f"Unsupported email file format: {filename}")


def _build_corpus(emails: list[EmailMessage]) -> str:
    """Build a text corpus from sent emails for embedding."""
    lines: list[str] = []
    for em in emails:
        parts = []
        if em.subject:
            parts.append(f"Subject: {em.subject}")
        if em.body_text:
            parts.append(em.body_text)
        if parts:
            lines.append("\n".join(parts))
    return "\n\n---\n\n".join(lines)


async def _extract_topics_via_llm(
    emails: list[EmailMessage],
) -> list[ExtractedSkill]:
    """Use LLM to extract professional topics/expertise from email subjects."""
    subjects = [
        em.subject for em in emails if em.subject and em.subject.strip()
    ]
    if not subjects:
        return []

    # Batch subjects into a single prompt (cap at 200 to stay within limits).
    subject_list = "\n".join(f"- {s}" for s in subjects[:200])
    messages: list[Message] = [
        {
            "role": "system",
            "content": (
                "You are an expert at identifying professional topics and "
                "skills from email subject lines. Analyze the following sent "
                "email subjects and extract the professional topics, skills, "
                "and areas of expertise they reveal about the sender. "
                "Return a JSON object with a single key \"skills\" containing "
                "an array of objects, each with \"name\" (the skill/topic), "
                "\"category\" (e.g. \"Domain\", \"Technology\", "
                "\"Communication\"), and \"quote\" (the subject line that "
                "best supports this skill). Return ONLY valid JSON."
            ),
        },
        {
            "role": "user",
            "content": f"Email subjects:\n{subject_list}",
        },
    ]

    llm = get_llm()
    result = await llm.complete(
        messages,
        model=settings.llm_model_strong,
        max_tokens=2048,
        temperature=0.1,
        json_mode=True,
        purpose="email_topic_extraction",
    )

    import json

    skills: list[ExtractedSkill] = []
    try:
        text = result.text.strip()
        # Handle markdown code fences.
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            text = text[start : end + 1]
        data = json.loads(text)
        raw_skills = data.get("skills", [])
        for item in raw_skills:
            if isinstance(item, dict) and item.get("name"):
                skills.append(
                    ExtractedSkill(
                        name=item["name"],
                        category=item.get("category"),
                        quote=item.get(
                            "quote", f"Email topic: {item['name']}"
                        ),
                    )
                )
    except (json.JSONDecodeError, KeyError, TypeError):
        log.warning("email_topic_extraction_parse_failed")

    return skills


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
            raise ValueError("No raw data attached to email source")
        filename = (source.stats or {}).get("filename", "export.mbox")

        # -- Parse --
        await _set_progress(sf, job_id, step="parsing", progress=0.2)
        emails = _parse_emails(raw, filename)
        if not emails:
            raise ValueError(
                "No sent emails found in the uploaded file"
            )

        # -- Build corpus and embed --
        await _set_progress(sf, job_id, step="embedding", progress=0.4)
        corpus = _build_corpus(emails)
        if corpus:
            content_hash = hashlib.sha256(corpus.encode()).hexdigest()
            doc = Document(
                source_id=source.id,
                persona_id=persona.id,
                title="Email corpus (sent)",
                mime="text/plain",
                content=corpus[:50000],  # cap stored content
                content_hash=content_hash,
                doc_metadata={"type": "email_corpus"},
            )
            s.add(doc)
            await s.flush()

            embedder = get_embedder()
            text_chunks = chunk_text(corpus)
            vectors = await embedder.embed(
                [tc.text for tc in text_chunks]
            )
            chunks_for_merge: list[tuple[uuid.UUID, str]] = []
            for tc, vec in zip(
                text_chunks, vectors, strict=True
            ):
                ch = Chunk(
                    document_id=doc.id,
                    persona_id=persona.id,
                    ordinal=tc.ordinal,
                    text=tc.text,
                    embedding=vec,
                    chunk_metadata={"type": "email"},
                )
                s.add(ch)
                await s.flush()
                chunks_for_merge.append((ch.id, ch.text))
        else:
            chunks_for_merge = []

        # -- Extract topics via LLM --
        await _set_progress(
            sf, job_id, step="extracting_topics", progress=0.6
        )
        llm_skills = await _extract_topics_via_llm(emails)

        # -- Build extraction --
        extraction = ResumeExtraction(skills=llm_skills)

        # -- Snapshot and merge --
        await snapshot_persona(
            s, persona, reason="Before email import"
        )
        await _set_progress(sf, job_id, step="merging", progress=0.8)
        summary = await merge_extraction(
            s,
            persona,
            extraction,
            source_id=source.id,
            chunks=chunks_for_merge,
            source_label="email",
            evidence_weight=_EMAIL_W,
        )

        await compute_completeness(s, persona)
        source.status = "synced"
        source.last_synced = datetime.now(UTC)
        stats = dict(source.stats or {})
        stats.pop("raw_data", None)
        stats["email_count"] = len(emails)
        stats["merged"] = summary.to_dict()["created"]
        source.stats = stats
        await s.commit()
        return summary.to_dict()
