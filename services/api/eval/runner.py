"""Evaluation runner (SRD §62): retrieval quality, groundedness, hallucination.

Metrics are computed against a synthetic persona so results are reproducible.
Retrieval and validation are deterministic, so these metrics hold even with the
fake provider (used in CI); the real provider can be swapped in to also judge
generation quality.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag.retrieval import retrieve
from app.ai.rag.validation import ClaimStatus, validate_claim
from app.domain.career import generate_resume
from app.models.persona import Persona
from eval.questions import (
    FABRICATED_CLAIMS,
    NEGATIVE_QUERIES,
    RETRIEVAL_QUERIES,
    SUPPORTED_CLAIMS,
)

JD = (
    "AI Engineer. Required: Python, FastAPI, PostgreSQL, RAG, NLP. "
    "Responsibilities: build LLM pipelines and backend services."
)


@dataclass
class EvalReport:
    retrieval_recall_at_k: float = 0.0
    retrieval_mrr: float = 0.0
    negative_accuracy: float = 0.0
    groundedness: float = 0.0
    hallucination_rate: float = 0.0
    supported_pass_rate: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


async def run_eval(session: AsyncSession, persona: Persona) -> EvalReport:
    report = EvalReport()

    # --- Retrieval recall@k and MRR ---
    hits, rr_sum = 0, 0.0
    for query, expected in RETRIEVAL_QUERIES:
        ctx = await retrieve(session, persona, query)
        ranked = [f"{f.label} {f.detail}".lower() for f in ctx.facts] + [
            c.text.lower() for c in ctx.chunks
        ]
        rank = next((i for i, text in enumerate(ranked, 1) if expected in text), 0)
        if rank:
            hits += 1
            rr_sum += 1.0 / rank
    n = len(RETRIEVAL_QUERIES)
    report.retrieval_recall_at_k = round(hits / n, 3)
    report.retrieval_mrr = round(rr_sum / n, 3)

    # --- Negative handling: absent terms must not surface as structured facts ---
    neg_ok = 0
    for query, absent in NEGATIVE_QUERIES:
        ctx = await retrieve(session, persona, query)
        fact_labels = " ".join(f.label.lower() for f in ctx.facts)
        if absent not in fact_labels:
            neg_ok += 1
    report.negative_accuracy = round(neg_ok / len(NEGATIVE_QUERIES), 3)

    # --- Groundedness: every resume bullet should be evidence-backed ---
    resume = await generate_resume(session, persona, JD)
    bullets = [
        b
        for section in (*resume["resume"]["experience"], *resume["resume"]["projects"])
        for b in section["bullets"]
    ]
    report.groundedness = round(
        sum(1 for b in bullets if b["validated"]) / len(bullets), 3
    ) if bullets else 1.0

    # --- Hallucination: fabricated claims validated against persona evidence ---
    corpus = await _evidence_corpus(session, persona)

    allowed_fab = sum(
        1
        for claim in FABRICATED_CLAIMS
        if validate_claim(claim, corpus).status == ClaimStatus.allow
    )
    report.hallucination_rate = round(allowed_fab / len(FABRICATED_CLAIMS), 3)

    allowed_sup = sum(
        1
        for claim in SUPPORTED_CLAIMS
        if validate_claim(claim, corpus).status != ClaimStatus.reject
    )
    report.supported_pass_rate = round(allowed_sup / len(SUPPORTED_CLAIMS), 3)

    report.details = {
        "retrieval_queries": len(RETRIEVAL_QUERIES),
        "negative_queries": len(NEGATIVE_QUERIES),
        "resume_bullets": len(bullets),
        "fabricated_claims": len(FABRICATED_CLAIMS),
        "evidence_chars": len(corpus),
    }
    return report


async def _evidence_corpus(session: AsyncSession, persona: Persona) -> str:
    """All of the persona's evidence + fact text, as the grounding corpus."""
    from sqlalchemy import select

    from app.models.evidence import Evidence
    from app.models.facts import Experience, Project, Skill

    parts: list[str] = []
    rows = await session.execute(
        select(Evidence.content).where(Evidence.persona_id == persona.id)
    )
    parts.extend(c for c in rows.scalars().all() if c)
    for model in (Skill, Project, Experience):
        items = await session.execute(
            select(model).where(model.persona_id == persona.id, model.deleted_at.is_(None))
        )
        for row in items.scalars().all():
            parts.append(getattr(row, "name", "") or getattr(row, "role", "") or "")
            parts.append(getattr(row, "description", "") or "")
            parts.extend(getattr(row, "technologies", []) or [])
    return " ".join(parts)
