"""PKM (bookmarks / notes) sync: parse, embed, extract, merge."""

from __future__ import annotations

import hashlib
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from app.ai.embeddings import get_embedder
from app.ai.extraction import ResumeExtraction
from app.ai.llm import LLMResult, complete_structured
from app.ai.llm.base import Message
from app.connectors.pkm import (
    Bookmark,
    Note,
    parse_bookmarks_html,
    parse_markdown_notes,
)
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

log = get_logger("pkm_sync")
_PKM_W = EVIDENCE_WEIGHTS.get("pkm", 0.3)


# ── LLM extraction prompts ────────────────────────────────────────

_BOOKMARKS_SYSTEM = """\
You extract interests and expertise areas from a person's browser \
bookmarks.

Given bookmark titles grouped by domain and tag, identify the \
topics, technologies, and fields the person is interested in \
or knowledgeable about.

Return a JSON object with:
- skills: list of {name, category, quote}
  - category should be "Interest"
  - quote should be a representative bookmark title

Output ONLY the JSON object."""

_NOTES_SYSTEM = """\
You extract skills and knowledge areas from a person's personal \
notes.

Given note contents, identify skills, technologies, and domains \
the person has knowledge of.

Return a JSON object with:
- skills: list of {name, category, quote}
  - category should be "Knowledge"
  - quote should be a short verbatim excerpt from the notes

Output ONLY the JSON object."""


class _SkillList(ResumeExtraction):
    """Thin wrapper so complete_structured returns skills only."""
    pass


# ── Job runner ─────────────────────────────────────────────────────


async def sync_pkm_job(
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
            "pkm_sync_failed",
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


# ── Internal logic ─────────────────────────────────────────────────


def _build_bookmark_corpus(
    bookmarks: list[Bookmark],
) -> str:
    """Group bookmarks by domain/tag for LLM consumption."""
    by_tag: dict[str, list[str]] = defaultdict(list)
    for bm in bookmarks:
        domain = urlparse(bm.url).netloc or "other"
        tags = bm.tags or [domain]
        for tag in tags:
            by_tag[tag].append(bm.title)

    lines: list[str] = []
    for tag, titles in sorted(by_tag.items()):
        lines.append(f"## {tag}")
        for t in titles[:50]:  # cap per group
            lines.append(f"- {t}")
        lines.append("")
    return "\n".join(lines)[:16000]


async def _extract_from_bookmarks(
    bookmarks: list[Bookmark],
) -> tuple[ResumeExtraction, LLMResult]:
    corpus = _build_bookmark_corpus(bookmarks)
    messages: list[Message] = [
        {"role": "system", "content": _BOOKMARKS_SYSTEM},
        {"role": "user", "content": f"Bookmarks:\n\n{corpus}"},
    ]
    return await complete_structured(
        _SkillList,
        messages,
        model=settings.llm_model_strong,
        max_tokens=4000,
        purpose="extract_pkm_bookmarks",
    )


async def _extract_from_notes(
    notes: list[Note],
) -> tuple[ResumeExtraction, LLMResult]:
    combined = "\n\n---\n\n".join(
        f"# {n.title}\n{n.content}" for n in notes
    )[:16000]
    messages: list[Message] = [
        {"role": "system", "content": _NOTES_SYSTEM},
        {"role": "user", "content": f"Notes:\n\n{combined}"},
    ]
    return await complete_structured(
        _SkillList,
        messages,
        model=settings.llm_model_strong,
        max_tokens=4000,
        purpose="extract_pkm_notes",
    )


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
                "No raw data attached to PKM source"
            )
        subtype = (source.stats or {}).get(
            "subtype", "bookmarks"
        )

        await _set_progress(
            sf, job_id, step="parsing", progress=0.2
        )
        raw_bytes = bytes.fromhex(raw)

        if subtype == "bookmarks":
            bookmarks = parse_bookmarks_html(raw_bytes)
            item_count = len(bookmarks)
        else:
            notes = parse_markdown_notes(raw_bytes)
            item_count = len(notes)

        # ── Embed as documents / chunks ──
        await _set_progress(
            sf, job_id, step="embedding", progress=0.4
        )
        embedder = get_embedder()
        chunks_for_merge: list[tuple[uuid.UUID, str]] = []

        if subtype == "bookmarks":
            corpus = _build_bookmark_corpus(bookmarks)
            doc = Document(
                source_id=source.id,
                persona_id=persona.id,
                title="Bookmarks corpus",
                mime="text/plain",
                content=corpus,
                content_hash=hashlib.sha256(
                    corpus.encode()
                ).hexdigest(),
                doc_metadata={"subtype": "bookmarks"},
            )
            s.add(doc)
            await s.flush()
            text_chunks = chunk_text(corpus)
            vectors = await embedder.embed(
                [c.text for c in text_chunks]
            )
            for c, vec in zip(
                text_chunks, vectors, strict=True
            ):
                ch = Chunk(
                    document_id=doc.id,
                    persona_id=persona.id,
                    ordinal=c.ordinal,
                    text=c.text,
                    embedding=vec,
                    chunk_metadata={
                        "source": "bookmarks",
                        "section": c.section,
                    },
                )
                s.add(ch)
                await s.flush()
                chunks_for_merge.append((ch.id, ch.text))
        else:
            for note in notes:
                doc = Document(
                    source_id=source.id,
                    persona_id=persona.id,
                    title=note.title,
                    mime="text/markdown",
                    content=note.content,
                    content_hash=hashlib.sha256(
                        note.content.encode()
                    ).hexdigest(),
                    doc_metadata={
                        "subtype": "notes",
                        "tags": note.tags,
                    },
                )
                s.add(doc)
                await s.flush()
                text_chunks = chunk_text(note.content)
                if not text_chunks:
                    continue
                vectors = await embedder.embed(
                    [c.text for c in text_chunks]
                )
                for c, vec in zip(
                    text_chunks, vectors, strict=True
                ):
                    ch = Chunk(
                        document_id=doc.id,
                        persona_id=persona.id,
                        ordinal=c.ordinal,
                        text=c.text,
                        embedding=vec,
                        chunk_metadata={
                            "source": "notes",
                            "note": note.title,
                            "section": c.section,
                        },
                    )
                    s.add(ch)
                    await s.flush()
                    chunks_for_merge.append(
                        (ch.id, ch.text)
                    )

        # ── LLM extraction ──
        await _set_progress(
            sf, job_id, step="extracting", progress=0.6
        )
        if subtype == "bookmarks":
            extraction, _ = await _extract_from_bookmarks(
                bookmarks
            )
            # Ensure category is "Interest"
            for sk in extraction.skills:
                sk.category = sk.category or "Interest"
        else:
            extraction, _ = await _extract_from_notes(notes)
            for sk in extraction.skills:
                sk.category = sk.category or "Knowledge"

        # Keep only skills from PKM extraction
        pkm_extraction = ResumeExtraction(
            skills=extraction.skills
        )

        await snapshot_persona(
            s,
            persona,
            reason=f"Before PKM {subtype} import",
        )

        # ── Merge ──
        await _set_progress(
            sf, job_id, step="merging", progress=0.8
        )
        summary = await merge_extraction(
            s,
            persona,
            pkm_extraction,
            source_id=source.id,
            chunks=chunks_for_merge,
            source_label="pkm",
            evidence_weight=_PKM_W,
        )

        await compute_completeness(s, persona)
        source.status = "synced"
        source.last_synced = datetime.now(UTC)
        stats = dict(source.stats or {})
        stats.pop("raw_data", None)
        stats["items"] = item_count
        stats["merged"] = summary.to_dict()["created"]
        source.stats = stats
        await s.commit()
        return summary.to_dict()
