"""Persona and persona-fact endpoints.

Facts of all kinds (skills, experience, projects, …) share one generic CRUD
implementation driven by a registry, so every type gets list/create/update/
delete, evidence viewing, and inferred-fact confirmation consistently.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_session
from app.core.errors import AppError, NotFoundError
from app.domain import persona as svc
from app.models.enums import EntityType, EvidenceState, Visibility
from app.models.facts import (
    Achievement,
    Certification,
    Education,
    Experience,
    Project,
    Publication,
    Skill,
)
from app.models.persona import KnowledgeArea, Preference
from app.models.user import User
from app.schemas import persona as S

router = APIRouter(prefix="/persona", tags=["persona"])


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FactConfig:
    model: Any
    entity_type: EntityType
    create_schema: type[BaseModel]
    update_schema: type[BaseModel]
    out_schema: type[BaseModel]


FACTS: dict[str, FactConfig] = {
    "skills": FactConfig(Skill, EntityType.skill, S.SkillCreate, S.SkillUpdate, S.SkillOut),
    "experiences": FactConfig(
        Experience, EntityType.experience, S.ExperienceCreate, S.ExperienceUpdate, S.ExperienceOut
    ),
    "projects": FactConfig(
        Project, EntityType.project, S.ProjectCreate, S.ProjectUpdate, S.ProjectOut
    ),
    "education": FactConfig(
        Education, EntityType.education, S.EducationCreate, S.EducationUpdate, S.EducationOut
    ),
    "achievements": FactConfig(
        Achievement, EntityType.achievement, S.AchievementCreate, S.AchievementUpdate,
        S.AchievementOut,
    ),
    "publications": FactConfig(
        Publication, EntityType.publication, S.PublicationCreate, S.PublicationUpdate,
        S.PublicationOut,
    ),
    "certifications": FactConfig(
        Certification, EntityType.certification, S.CertificationCreate, S.CertificationUpdate,
        S.CertificationOut,
    ),
    "preferences": FactConfig(
        Preference, EntityType.preference, S.PreferenceCreate, S.PreferenceUpdate, S.PreferenceOut
    ),
    "knowledge-areas": FactConfig(
        KnowledgeArea, EntityType.knowledge_area, S.KnowledgeAreaCreate, S.KnowledgeAreaUpdate,
        S.KnowledgeAreaOut,
    ),
}


def _cfg(resource: str) -> FactConfig:
    cfg = FACTS.get(resource)
    if cfg is None:
        raise NotFoundError(f"Unknown persona resource '{resource}'")
    return cfg


def _validate(schema: type[BaseModel], body: dict[str, Any]) -> BaseModel:
    try:
        return schema.model_validate(body)
    except ValidationError as exc:
        raise AppError(
            "Request validation failed",
            code="validation_error",
            status_code=422,
            details={"errors": exc.errors()},
        ) from exc


def canonicalize_skill(name: str) -> str:
    base = name.strip().lower()
    aliases = {
        "reactjs": "react",
        "react.js": "react",
        "nextjs": "next.js",
        "node": "node.js",
        "nodejs": "node.js",
        "postgres": "postgresql",
        "py": "python",
        "golang": "go",
    }
    return aliases.get(base, base)


# ---------------------------------------------------------------------------
# Persona root
# ---------------------------------------------------------------------------


async def _persona_for(session: AsyncSession, user: User):  # type: ignore[no-untyped-def]
    return await svc.get_or_create_persona(session, user.id)


@router.get("", response_model=S.PersonaOut)
async def get_persona(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> S.PersonaOut:
    persona = await _persona_for(session, user)
    await svc.compute_completeness(session, persona)
    return S.PersonaOut.model_validate(persona)


@router.patch("", response_model=S.PersonaOut)
async def update_persona(
    body: S.PersonaUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> S.PersonaOut:
    persona = await _persona_for(session, user)
    await svc.snapshot_persona(session, persona, reason="Updated identity")
    data = body.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(persona, field, value)
    await svc.compute_completeness(session, persona)
    # Flush to persist, then refresh to load the server-side updated_at before
    # serializing (otherwise Pydantic triggers lazy IO on the expired column).
    await session.flush()
    await session.refresh(persona)
    return S.PersonaOut.model_validate(persona)


@router.get("/full")
async def get_persona_full(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Persona plus every fact list — the payload the editor/dashboard loads."""
    persona = await _persona_for(session, user)
    await svc.compute_completeness(session, persona)
    out: dict[str, Any] = {"persona": S.PersonaOut.model_validate(persona).model_dump(mode="json")}
    facts: dict[str, Any] = {}
    for resource, cfg in FACTS.items():
        rows = await _list_rows(session, persona.id, cfg)
        facts[resource] = [
            cfg.out_schema.model_validate(r).model_dump(mode="json") for r in rows
        ]
    out["facts"] = facts
    return out


# ---------------------------------------------------------------------------
# Generic fact CRUD
# ---------------------------------------------------------------------------


async def _list_rows(session: AsyncSession, persona_id: uuid.UUID, cfg: FactConfig) -> list[Any]:
    result = await session.execute(
        select(cfg.model)
        .where(cfg.model.persona_id == persona_id, cfg.model.deleted_at.is_(None))
        .order_by(cfg.model.created_at.desc())
    )
    return list(result.scalars().all())


async def _get_row(  # type: ignore[no-untyped-def]
    session: AsyncSession, persona_id: uuid.UUID, cfg: FactConfig, fact_id: uuid.UUID
):
    row = await session.get(cfg.model, fact_id)
    if row is None or row.persona_id != persona_id or row.deleted_at is not None:
        raise NotFoundError("Fact not found")
    return row


@router.get("/{resource}")
async def list_facts(
    resource: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    cfg = _cfg(resource)
    persona = await _persona_for(session, user)
    rows = await _list_rows(session, persona.id, cfg)
    return [cfg.out_schema.model_validate(r).model_dump(mode="json") for r in rows]


@router.post("/{resource}", status_code=201)
async def create_fact(
    resource: str,
    body: dict[str, Any],
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    cfg = _cfg(resource)
    persona = await _persona_for(session, user)
    payload = _validate(cfg.create_schema, body).model_dump()

    if cfg.model is Skill:
        payload["canonical_name"] = canonicalize_skill(payload["name"])

    # Manual entries are user-confirmed with full confidence.
    row = cfg.model(
        persona_id=persona.id,
        state=EvidenceState.user_confirmed,
        confidence=svc.EVIDENCE_WEIGHTS["user"],
        **payload,
    )
    session.add(row)
    await session.flush()

    await svc.add_manual_evidence(
        session, persona_id=persona.id, entity_type=cfg.entity_type, entity_id=row.id
    )
    await svc.recompute_fact_confidence(session, row, cfg.entity_type)
    await svc.compute_completeness(session, persona)
    return cfg.out_schema.model_validate(row).model_dump(mode="json")


@router.patch("/{resource}/{fact_id}")
async def update_fact(
    resource: str,
    fact_id: uuid.UUID,
    body: dict[str, Any],
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    cfg = _cfg(resource)
    persona = await _persona_for(session, user)
    row = await _get_row(session, persona.id, cfg, fact_id)
    data = _validate(cfg.update_schema, body).model_dump(exclude_unset=True)

    for field, value in data.items():
        setattr(row, field, value)
    if cfg.model is Skill and "name" in data and data["name"]:
        row.canonical_name = canonicalize_skill(data["name"])
    await session.flush()
    await session.refresh(row)
    return cfg.out_schema.model_validate(row).model_dump(mode="json")


@router.delete("/{resource}/{fact_id}", status_code=204)
async def delete_fact(
    resource: str,
    fact_id: uuid.UUID,
    response: Response,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    from datetime import UTC, datetime

    cfg = _cfg(resource)
    persona = await _persona_for(session, user)
    row = await _get_row(session, persona.id, cfg, fact_id)
    row.deleted_at = datetime.now(UTC)
    await session.flush()
    await svc.compute_completeness(session, persona)
    response.status_code = 204
    return response


@router.post("/{resource}/{fact_id}/confirm")
async def confirm_fact(
    resource: str,
    fact_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Confirm an inferred fact (SRD §22): mark user-confirmed, add evidence."""
    cfg = _cfg(resource)
    persona = await _persona_for(session, user)
    row = await _get_row(session, persona.id, cfg, fact_id)
    row.state = EvidenceState.user_confirmed
    await svc.add_manual_evidence(
        session,
        persona_id=persona.id,
        entity_type=cfg.entity_type,
        entity_id=row.id,
        note="Confirmed by the user",
    )
    await svc.recompute_fact_confidence(session, row, cfg.entity_type)
    await session.flush()
    await session.refresh(row)
    return cfg.out_schema.model_validate(row).model_dump(mode="json")


@router.get("/{resource}/{fact_id}/evidence", response_model=list[S.EvidenceOut])
async def fact_evidence(
    resource: str,
    fact_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[S.EvidenceOut]:
    cfg = _cfg(resource)
    persona = await _persona_for(session, user)
    await _get_row(session, persona.id, cfg, fact_id)
    items = await svc.evidence_for(session, cfg.entity_type, fact_id)
    return [S.EvidenceOut.model_validate(e) for e in items]


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------


@router.get("/meta/versions", response_model=list[S.PersonaVersionOut])
async def list_persona_versions(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[S.PersonaVersionOut]:
    persona = await _persona_for(session, user)
    versions = await svc.list_versions(session, persona)
    return [S.PersonaVersionOut.model_validate(v) for v in versions]


@router.post("/meta/versions/{version_id}/restore", response_model=S.PersonaOut)
async def restore_persona_version(
    version_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> S.PersonaOut:
    persona = await _persona_for(session, user)
    restored = await svc.restore_version(session, persona, version_id)
    await session.flush()
    await session.refresh(restored)
    return S.PersonaOut.model_validate(restored)


_ = Visibility  # re-export for schema consumers
