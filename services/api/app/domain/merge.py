"""Merge extracted facts into a persona (SRD §46, §47).

For each extracted fact we canonicalize, look for an existing matching fact,
then either attach evidence to it or create it. Single-valued identity fields
that disagree with what the persona already holds raise a Conflict for the user
to resolve rather than being silently overwritten.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.extraction import ResumeExtraction
from app.domain.persona import EVIDENCE_WEIGHTS, compute_confidence
from app.models.enums import EntityType, EvidenceState
from app.models.evidence import Evidence
from app.models.facts import Achievement, Education, Experience, Project, Skill
from app.models.ingestion import Conflict
from app.models.persona import Persona

_RESUME_W = EVIDENCE_WEIGHTS["resume"]


@dataclass
class MergeSummary:
    created: dict[str, int] = field(default_factory=dict)
    updated: dict[str, int] = field(default_factory=dict)
    evidence_added: int = 0
    conflicts: int = 0

    def bump(self, bucket: dict[str, int], key: str) -> None:
        bucket[key] = bucket.get(key, 0) + 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "created": self.created,
            "updated": self.updated,
            "evidence_added": self.evidence_added,
            "conflicts": self.conflicts,
        }


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def _similar(a: str, b: str, threshold: float = 0.9) -> bool:
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return False
    if a == b:
        return True
    return SequenceMatcher(None, a, b).ratio() >= threshold


def _canonical_skill(name: str) -> str:
    base = name.strip().lower()
    aliases = {
        "reactjs": "react", "react.js": "react", "nextjs": "next.js",
        "node": "node.js", "nodejs": "node.js", "postgres": "postgresql",
        "py": "python", "golang": "go",
    }
    return aliases.get(base, base)


def _find_chunk(quote: str, chunks: list[tuple[uuid.UUID, str]]) -> uuid.UUID | None:
    q = _norm(quote)
    if not q:
        return None
    for cid, ctext in chunks:
        if q in _norm(ctext):
            return cid
    # Fall back to best token overlap.
    best, best_score = None, 0.0
    for cid, ctext in chunks:
        score = SequenceMatcher(None, q, _norm(ctext)).ratio()
        if score > best_score:
            best, best_score = cid, score
    return best if best_score > 0.4 else (chunks[0][0] if chunks else None)


async def merge_extraction(
    session: AsyncSession,
    persona: Persona,
    extraction: ResumeExtraction,
    *,
    source_id: uuid.UUID,
    chunks: list[tuple[uuid.UUID, str]],
) -> MergeSummary:
    summary = MergeSummary()

    async def add_evidence(
        entity_type: EntityType, entity_id: uuid.UUID, quote: str, section: str
    ) -> None:
        ev = Evidence(
            persona_id=persona.id,
            entity_type=entity_type,
            entity_id=entity_id,
            source_id=source_id,
            chunk_id=_find_chunk(quote, chunks),
            content=quote,
            locator={"source": "resume", "section": section},
            state=EvidenceState.verified,
            confidence=_RESUME_W,
        )
        session.add(ev)
        summary.evidence_added += 1

    async def recompute(fact: Any, entity_type: EntityType) -> None:
        # Flush so the just-added evidence is counted (autoflush is off).
        await session.flush()
        result = await session.execute(
            select(Evidence.confidence).where(
                Evidence.entity_type == entity_type, Evidence.entity_id == fact.id
            )
        )
        weights = list(result.scalars().all())
        fact.confidence = compute_confidence(weights)
        if hasattr(fact, "evidence_count"):
            fact.evidence_count = len(weights)

    # ---- Identity (conflict-aware) ----
    await _merge_identity(session, persona, extraction, summary)

    # ---- Skills ----
    existing_skills = await _load(session, Skill, persona.id)
    for sk in extraction.skills:
        canon = _canonical_skill(sk.name)
        match = next((s for s in existing_skills if s.canonical_name == canon), None)
        if match is None:
            match = Skill(
                persona_id=persona.id, name=sk.name, canonical_name=canon,
                category=sk.category, state=EvidenceState.verified, confidence=_RESUME_W,
            )
            session.add(match)
            await session.flush()
            existing_skills.append(match)
            summary.bump(summary.created, "skills")
        else:
            summary.bump(summary.updated, "skills")
        await add_evidence(EntityType.skill, match.id, sk.quote, "skills")
        await recompute(match, EntityType.skill)

    # ---- Experiences ----
    existing_exp = await _load(session, Experience, persona.id)
    for ex in extraction.experiences:
        match = next(
            (
                e for e in existing_exp
                if _similar(e.role, ex.role) and _similar(e.company or "", ex.company or "")
            ),
            None,
        )
        if match is None:
            match = Experience(
                persona_id=persona.id, role=ex.role, company=ex.company,
                description=ex.description, state=EvidenceState.verified, confidence=_RESUME_W,
            )
            session.add(match)
            await session.flush()
            existing_exp.append(match)
            summary.bump(summary.created, "experiences")
        else:
            if not match.description and ex.description:
                match.description = ex.description
            summary.bump(summary.updated, "experiences")
        await add_evidence(EntityType.experience, match.id, ex.quote, "experience")
        await recompute(match, EntityType.experience)

    # ---- Projects ----
    existing_proj = await _load(session, Project, persona.id)
    for pr in extraction.projects:
        match = next((p for p in existing_proj if _similar(p.name, pr.name)), None)
        if match is None:
            match = Project(
                persona_id=persona.id, name=pr.name, description=pr.description,
                technologies=pr.technologies, state=EvidenceState.verified, confidence=_RESUME_W,
            )
            session.add(match)
            await session.flush()
            existing_proj.append(match)
            summary.bump(summary.created, "projects")
        else:
            merged = sorted(set(match.technologies) | set(pr.technologies))
            match.technologies = merged
            summary.bump(summary.updated, "projects")
        await add_evidence(EntityType.project, match.id, pr.quote, "projects")
        await recompute(match, EntityType.project)

    # ---- Education ----
    existing_edu = await _load(session, Education, persona.id)
    for ed in extraction.education:
        match = next((e for e in existing_edu if _similar(e.institution, ed.institution)), None)
        if match is None:
            match = Education(
                persona_id=persona.id, institution=ed.institution, degree=ed.degree,
                field_of_study=ed.field_of_study,
                state=EvidenceState.verified,
                confidence=_RESUME_W,
            )
            session.add(match)
            await session.flush()
            existing_edu.append(match)
            summary.bump(summary.created, "education")
        else:
            summary.bump(summary.updated, "education")
        await add_evidence(EntityType.education, match.id, ed.quote, "education")
        await recompute(match, EntityType.education)

    # ---- Achievements ----
    existing_ach = await _load(session, Achievement, persona.id)
    for ac in extraction.achievements:
        match = next((a for a in existing_ach if _similar(a.title, ac.title)), None)
        if match is None:
            match = Achievement(
                persona_id=persona.id, title=ac.title,
                state=EvidenceState.verified, confidence=_RESUME_W,
            )
            session.add(match)
            await session.flush()
            existing_ach.append(match)
            summary.bump(summary.created, "achievements")
        else:
            summary.bump(summary.updated, "achievements")
        await add_evidence(EntityType.achievement, match.id, ac.quote, "achievements")
        await recompute(match, EntityType.achievement)

    await session.flush()
    return summary


async def _load(session: AsyncSession, model: Any, persona_id: uuid.UUID) -> list[Any]:
    result = await session.execute(
        select(model).where(model.persona_id == persona_id, model.deleted_at.is_(None))
    )
    return list(result.scalars().all())


async def _merge_identity(
    session: AsyncSession, persona: Persona, extraction: ResumeExtraction, summary: MergeSummary
) -> None:
    """Fill empty identity fields; raise a conflict when a single-valued field
    disagrees with what the persona already holds (SRD §47)."""
    for field_name in ("full_name", "headline", "location"):
        new_val = getattr(extraction, field_name)
        if not new_val:
            continue
        current = getattr(persona, field_name)
        if not current:
            setattr(persona, field_name, new_val)
        elif _norm(current) != _norm(new_val) and not _similar(current, new_val, 0.95):
            await _raise_conflict(session, persona, field_name, current, new_val, summary)

    # Summary is free text: only fill when empty, never conflict.
    if extraction.summary and not persona.summary:
        persona.summary = extraction.summary


async def _raise_conflict(
    session: AsyncSession,
    persona: Persona,
    field_name: str,
    current: str,
    new_val: str,
    summary: MergeSummary,
) -> None:
    # Avoid duplicate open conflicts for the same field+candidate.
    result = await session.execute(
        select(Conflict).where(
            Conflict.persona_id == persona.id,
            Conflict.field == field_name,
            Conflict.status == "open",
        )
    )
    if result.scalar_one_or_none() is not None:
        return
    session.add(
        Conflict(
            persona_id=persona.id,
            field=field_name,
            candidates=[
                {"value": current, "source": "existing"},
                {"value": new_val, "source": "resume"},
            ],
            status="open",
        )
    )
    summary.conflicts += 1
