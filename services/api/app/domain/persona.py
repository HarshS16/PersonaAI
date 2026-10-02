"""Persona domain logic: bootstrap, confidence, completeness, evidence, and
version snapshots/restore.

Confidence (SRD §48): a fact's confidence is 1 - Π(1 - wᵢ) over its evidence
items, where wᵢ is the weight of each evidence item by source kind.

Completeness (SRD §21): a weighted measure of how much of the persona is filled
in, plus the share of facts that carry evidence.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.enums import EntityType, EvidenceState
from app.models.evidence import Evidence
from app.models.facts import (
    Achievement,
    Certification,
    Education,
    Experience,
    Project,
    Publication,
    Skill,
)
from app.models.persona import KnowledgeArea, Persona, PersonaVersion, Preference

# Evidence weight by source kind (SRD §48). Used to combine evidence into a
# single confidence score.
EVIDENCE_WEIGHTS: dict[str, float] = {
    "user": 1.0,
    "resume": 0.6,
    "github_code": 0.5,
    "github_language": 0.5,
    "github_readme": 0.35,
    "inferred": 0.25,
}


def compute_confidence(weights: list[float]) -> float:
    """Combine independent evidence weights: 1 - Π(1 - w)."""
    product = 1.0
    for w in weights:
        product *= 1.0 - max(0.0, min(1.0, w))
    return round(1.0 - product, 4)


async def get_or_create_persona(session: AsyncSession, user_id: uuid.UUID) -> Persona:
    result = await session.execute(select(Persona).where(Persona.user_id == user_id))
    persona = result.scalar_one_or_none()
    if persona is None:
        persona = Persona(user_id=user_id)
        session.add(persona)
        await session.flush()
    return persona


async def add_manual_evidence(
    session: AsyncSession,
    *,
    persona_id: uuid.UUID,
    entity_type: EntityType,
    entity_id: uuid.UUID,
    note: str | None = None,
) -> Evidence:
    """Manual entries are their own evidence: user-confirmed, full weight."""
    ev = Evidence(
        persona_id=persona_id,
        entity_type=entity_type,
        entity_id=entity_id,
        content=note or "Entered manually by the user",
        locator={"origin": "manual"},
        state=EvidenceState.user_confirmed,
        confidence=EVIDENCE_WEIGHTS["user"],
    )
    session.add(ev)
    await session.flush()
    return ev


async def evidence_for(
    session: AsyncSession, entity_type: EntityType, entity_id: uuid.UUID
) -> list[Evidence]:
    result = await session.execute(
        select(Evidence)
        .where(Evidence.entity_type == entity_type, Evidence.entity_id == entity_id)
        .order_by(Evidence.created_at)
    )
    return list(result.scalars().all())


async def recompute_fact_confidence(
    session: AsyncSession, fact: Any, entity_type: EntityType
) -> None:
    """Recompute a fact's confidence from its current evidence."""
    items = await evidence_for(session, entity_type, fact.id)
    if not items:
        return
    fact.confidence = compute_confidence([e.confidence for e in items])
    if hasattr(fact, "evidence_count"):
        fact.evidence_count = len(items)


_ENTITY_MODELS: dict[EntityType, Any] = {}


def _entity_models() -> dict[EntityType, Any]:
    if not _ENTITY_MODELS:
        from app.models.facts import (
            Achievement,
            Certification,
            Education,
            Experience,
            Project,
            Publication,
            Skill,
        )

        _ENTITY_MODELS.update(
            {
                EntityType.skill: Skill,
                EntityType.experience: Experience,
                EntityType.project: Project,
                EntityType.education: Education,
                EntityType.achievement: Achievement,
                EntityType.publication: Publication,
                EntityType.certification: Certification,
                EntityType.preference: Preference,
                EntityType.knowledge_area: KnowledgeArea,
            }
        )
    return _ENTITY_MODELS


async def recompute_entities(
    session: AsyncSession, refs: set[tuple[EntityType, uuid.UUID]]
) -> None:
    """After evidence changes, recompute confidence for the affected facts.

    A fact that has lost all its evidence drops to the inferred state with low
    confidence rather than being deleted (the user may still want it).
    """
    models = _entity_models()
    for entity_type, entity_id in refs:
        model = models.get(entity_type)
        if model is None:
            continue
        fact = await session.get(model, entity_id)
        if fact is None:
            continue
        items = await evidence_for(session, entity_type, entity_id)
        if items:
            fact.confidence = compute_confidence([e.confidence for e in items])
        else:
            fact.confidence = EVIDENCE_WEIGHTS["inferred"]
            fact.state = EvidenceState.inferred
        if hasattr(fact, "evidence_count"):
            fact.evidence_count = len(items)


# ---------------------------------------------------------------------------
# Completeness
# ---------------------------------------------------------------------------

_COMPLETENESS_WEIGHTS = {
    "identity": 0.15,
    "experience": 0.2,
    "education": 0.1,
    "skills": 0.2,
    "projects": 0.15,
    "achievements": 0.05,
    "preferences": 0.05,
    "evidence_ratio": 0.1,
}


async def _count(session: AsyncSession, model: Any, persona_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(model)
        .where(model.persona_id == persona_id, model.deleted_at.is_(None))
    )
    return int(result.scalar_one())


async def compute_completeness(session: AsyncSession, persona: Persona) -> float:
    pid = persona.id
    identity_filled = sum(
        bool(x) for x in (persona.full_name, persona.headline, persona.summary)
    )
    scores = {
        "identity": identity_filled / 3,
        "experience": min(await _count(session, Experience, pid), 1),
        "education": min(await _count(session, Education, pid), 1),
        "skills": min(await _count(session, Skill, pid) / 5, 1),
        "projects": min(await _count(session, Project, pid) / 2, 1),
        "achievements": min(await _count(session, Achievement, pid), 1),
        "preferences": min(await _count(session, Preference, pid), 1),
    }

    total_facts = 0
    for m in (Skill, Experience, Project, Education, Achievement, Publication, Certification):
        total_facts += await _count(session, m, pid)
    ev_result = await session.execute(
        select(func.count(func.distinct(Evidence.entity_id))).where(Evidence.persona_id == pid)
    )
    facts_with_evidence = int(ev_result.scalar_one())
    scores["evidence_ratio"] = (facts_with_evidence / total_facts) if total_facts else 0.0

    completeness = sum(scores[k] * w for k, w in _COMPLETENESS_WEIGHTS.items())
    persona.completeness = round(completeness, 4)
    return persona.completeness


# ---------------------------------------------------------------------------
# Serialization / versioning
# ---------------------------------------------------------------------------

_SERIALIZE_FIELDS: dict[str, tuple[Any, tuple[str, ...]]] = {
    "skills": (Skill, ("name", "canonical_name", "category", "evidence_count")),
    "experiences": (
        Experience,
        ("company", "role", "employment_type", "location", "start_date", "end_date",
         "is_current", "description", "highlights"),
    ),
    "projects": (
        Project,
        ("name", "description", "role", "technologies", "outcomes", "repository_url",
         "url", "start_date", "end_date"),
    ),
    "education": (
        Education,
        ("institution", "degree", "field_of_study", "start_date", "end_date", "grade",
         "description"),
    ),
    "achievements": (Achievement, ("title", "description", "date_awarded", "issuer")),
    "publications": (Publication, ("title", "venue", "year", "url", "authors", "description")),
    "certifications": (
        Certification,
        ("name", "issuer", "issue_date", "expiry_date", "credential_id", "url"),
    ),
    "preferences": (Preference, ("key", "value", "source")),
    "knowledge_areas": (KnowledgeArea, ("name", "parent_id")),
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


async def serialize_persona(session: AsyncSession, persona: Persona) -> dict[str, Any]:
    """Full persona snapshot used for versioning and (M8) export."""
    data: dict[str, Any] = {
        "persona": {
            "full_name": persona.full_name,
            "headline": persona.headline,
            "summary": persona.summary,
            "location": persona.location,
            "links": persona.links,
        },
        "facts": {},
    }
    common = ("visibility", "state", "confidence")
    for key, (model, fields) in _SERIALIZE_FIELDS.items():
        result = await session.execute(
            select(model).where(model.persona_id == persona.id, model.deleted_at.is_(None))
        )
        rows: list[dict[str, Any]] = []
        scalar_rows: list[Any] = list(result.scalars().all())
        for row in scalar_rows:
            record = {f: _json_safe(getattr(row, f)) for f in fields}
            record.update({c: _json_safe(getattr(row, c)) for c in common})
            rows.append(record)
        data["facts"][key] = rows
    return data


async def snapshot_persona(
    session: AsyncSession, persona: Persona, *, reason: str
) -> PersonaVersion:
    snapshot = await serialize_persona(session, persona)
    pv = PersonaVersion(
        persona_id=persona.id,
        version=persona.version,
        reason=reason,
        snapshot=snapshot,
    )
    session.add(pv)
    persona.version += 1
    await session.flush()
    return pv


async def list_versions(session: AsyncSession, persona: Persona) -> list[PersonaVersion]:
    result = await session.execute(
        select(PersonaVersion)
        .where(PersonaVersion.persona_id == persona.id)
        .order_by(PersonaVersion.version.desc())
    )
    return list(result.scalars().all())


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value) if isinstance(value, str) else value


async def restore_version(
    session: AsyncSession, persona: Persona, version_id: uuid.UUID
) -> Persona:
    """Restore a persona to a prior snapshot.

    The current state is snapshotted first (so a restore is itself reversible),
    then all fact rows are hard-deleted and recreated from the target snapshot.
    """
    pv = await session.get(PersonaVersion, version_id)
    if pv is None or pv.persona_id != persona.id:
        raise NotFoundError("Persona version not found")

    await snapshot_persona(session, persona, reason=f"Auto-snapshot before restoring v{pv.version}")

    snap = pv.snapshot
    ident = snap.get("persona", {})
    persona.full_name = ident.get("full_name")
    persona.headline = ident.get("headline")
    persona.summary = ident.get("summary")
    persona.location = ident.get("location")
    persona.links = ident.get("links") or {}

    # Evidence refers to facts by id; since we recreate facts with new ids, the
    # old evidence would orphan. Snapshots don't carry evidence, so clear it.
    await session.execute(delete(Evidence).where(Evidence.persona_id == persona.id))

    # Replace all facts.
    for key, (model, _fields) in _SERIALIZE_FIELDS.items():
        await session.execute(delete(model).where(model.persona_id == persona.id))
        for record in snap.get("facts", {}).get(key, []):
            payload = dict(record)
            for df in ("start_date", "end_date", "date_awarded", "issue_date", "expiry_date"):
                if df in payload:
                    payload[df] = _parse_date(payload[df])
            # Parent references point at pre-restore ids; drop them to avoid FK
            # violations (knowledge-area hierarchy is rebuilt manually if needed).
            payload.pop("parent_id", None)
            session.add(model(persona_id=persona.id, **payload))

    await session.flush()
    await compute_completeness(session, persona)
    persona.updated_at = datetime.now(UTC)
    return persona
