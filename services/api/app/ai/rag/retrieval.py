"""Persona-aware retrieval (SRD §16, §17).

Combines three signals, scoped to one persona:
  1. Structured facts   — SQL over skills/projects/experience/education
  2. Semantic chunks    — pgvector cosine search over document chunks
  3. Keyword chunks     — Postgres full-text (tsvector) search

Semantic and keyword chunk hits are fused with reciprocal rank fusion (RRF).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import get_embedder
from app.models.facts import Education, Experience, Project, Skill
from app.models.ingestion import Chunk, Document, Source
from app.models.persona import Persona


@dataclass
class ChunkHit:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    text: str
    score: float
    source_title: str | None = None
    source_type: str | None = None


@dataclass
class FactHit:
    entity_type: str
    entity_id: uuid.UUID
    label: str
    detail: str
    confidence: float


@dataclass
class RetrievedContext:
    facts: list[FactHit] = field(default_factory=list)
    chunks: list[ChunkHit] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.facts and not self.chunks


def _tokens(query: str) -> list[str]:
    return [t for t in query.lower().replace("?", " ").replace(",", " ").split() if len(t) > 2]


async def retrieve_structured(
    session: AsyncSession, persona: Persona, query: str, *, limit: int = 12
) -> list[FactHit]:
    toks = _tokens(query)
    if not toks:
        return []
    hits: list[FactHit] = []

    # Skills
    skill_rows = (
        await session.execute(
            select(Skill).where(Skill.persona_id == persona.id, Skill.deleted_at.is_(None))
        )
    ).scalars().all()
    for s in skill_rows:
        if any(t in s.canonical_name or s.canonical_name in t for t in toks):
            hits.append(
                FactHit("skill", s.id, s.name, f"Skill ({s.category or 'general'})", s.confidence)
            )

    # Projects
    proj_rows = (
        await session.execute(
            select(Project).where(Project.persona_id == persona.id, Project.deleted_at.is_(None))
        )
    ).scalars().all()
    for p in proj_rows:
        hay = f"{p.name} {p.description or ''} {' '.join(p.technologies)}".lower()
        if any(t in hay for t in toks):
            detail = (p.description or "")[:200]
            if p.technologies:
                detail += f" [tech: {', '.join(p.technologies)}]"
            hits.append(FactHit("project", p.id, p.name, detail.strip(), p.confidence))

    # Experience
    exp_rows = (
        await session.execute(
            select(Experience).where(
                Experience.persona_id == persona.id, Experience.deleted_at.is_(None)
            )
        )
    ).scalars().all()
    for e in exp_rows:
        hay = f"{e.role} {e.company or ''} {e.description or ''}".lower()
        if any(t in hay for t in toks):
            hits.append(
                FactHit("experience", e.id, f"{e.role} at {e.company or 'n/a'}",
                        (e.description or "")[:200], e.confidence)
            )

    # Education
    edu_rows = (
        await session.execute(
            select(Education).where(
                Education.persona_id == persona.id, Education.deleted_at.is_(None)
            )
        )
    ).scalars().all()
    for ed in edu_rows:
        hay = f"{ed.institution} {ed.degree or ''} {ed.field_of_study or ''}".lower()
        if any(t in hay for t in toks):
            hits.append(
                FactHit("education", ed.id, ed.institution,
                        f"{ed.degree or ''} {ed.field_of_study or ''}".strip(), ed.confidence)
            )

    return hits[:limit]


async def retrieve_semantic(
    session: AsyncSession, persona: Persona, query: str, *, k: int = 6
) -> list[ChunkHit]:
    embedder = get_embedder()
    qvec = await embedder.embed_one(query)

    # Vector search (cosine distance; smaller is closer).
    vec_rows = (
        await session.execute(
            select(
                Chunk.id,
                Chunk.document_id,
                Chunk.text,
                Chunk.embedding.cosine_distance(qvec).label("dist"),
            )
            .where(Chunk.persona_id == persona.id, Chunk.embedding.is_not(None))
            .order_by(text("dist"))
            .limit(k * 2)
        )
    ).all()
    vector_ranked = [(r.id, r.document_id, r.text) for r in vec_rows]

    # Keyword search (full-text).
    kw_rows = (
        await session.execute(
            select(Chunk.id, Chunk.document_id, Chunk.text)
            .where(
                Chunk.persona_id == persona.id,
                Chunk.tsv.op("@@")(func.plainto_tsquery("english", query)),
            )
            .order_by(
                func.ts_rank(Chunk.tsv, func.plainto_tsquery("english", query)).desc()
            )
            .limit(k * 2)
        )
    ).all()
    keyword_ranked = [(r.id, r.document_id, r.text) for r in kw_rows]

    # Reciprocal rank fusion.
    scores: dict[uuid.UUID, float] = {}
    meta: dict[uuid.UUID, tuple[uuid.UUID, str]] = {}
    for ranked in (vector_ranked, keyword_ranked):
        for rank, (cid, did, ctext) in enumerate(ranked):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (60 + rank)
            meta[cid] = (did, ctext)

    fused = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:k]

    # Attach source titles.
    hits: list[ChunkHit] = []
    for cid, score in fused:
        did, ctext = meta[cid]
        doc = await session.get(Document, did)
        src = await session.get(Source, doc.source_id) if doc else None
        hits.append(
            ChunkHit(
                chunk_id=cid,
                document_id=did,
                text=ctext,
                score=round(score, 5),
                source_title=(doc.title if doc else None),
                source_type=(src.type if src else None),
            )
        )
    return hits


async def retrieve(
    session: AsyncSession, persona: Persona, query: str
) -> RetrievedContext:
    facts = await retrieve_structured(session, persona, query)
    chunks = await retrieve_semantic(session, persona, query)
    return RetrievedContext(facts=facts, chunks=chunks)


def build_context_block(ctx: RetrievedContext) -> str:
    """Render retrieved context for the LLM prompt."""
    parts: list[str] = []
    if ctx.facts:
        parts.append("STRUCTURED FACTS:")
        for f in ctx.facts:
            parts.append(
                f"- [{f.entity_type}] {f.label}: {f.detail} (confidence {f.confidence:.2f})"
            )
    if ctx.chunks:
        parts.append("\nSOURCE EXCERPTS:")
        for i, c in enumerate(ctx.chunks, 1):
            label = c.source_title or c.source_type or "source"
            parts.append(f"[{i}] ({label}) {c.text[:600]}")
    return "\n".join(parts) if parts else "(no persona data found)"
