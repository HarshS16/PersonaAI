"""Preference inference (SRD §8.7): auto-detect work/career preferences from
persona data (experiences, skills, projects) and surface them for confirmation.

This is deterministic — no LLM needed. We look at patterns:
- Industry preferences from experience descriptions / company types
- Technology preferences from top-weighted skills
- Work-type preferences (remote, hybrid) from descriptions
- Seniority level from most recent role titles
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PreferenceSource
from app.models.facts import Experience, Skill
from app.models.persona import Persona, Preference

# Role-level heuristics
_SENIOR_PATTERN = re.compile(
    r"\b(senior|sr\.?|staff|principal|lead|director|vp|head of|chief|architect)\b",
    re.IGNORECASE,
)
_JUNIOR_PATTERN = re.compile(
    r"\b(junior|jr\.?|intern|entry.level|trainee|associate)\b",
    re.IGNORECASE,
)

# Remote/hybrid heuristics
_REMOTE_PATTERN = re.compile(r"\b(remote|distributed|work.from.home|wfh)\b", re.IGNORECASE)
_HYBRID_PATTERN = re.compile(r"\b(hybrid|flexible.location)\b", re.IGNORECASE)


async def infer_preferences(
    session: AsyncSession, persona: Persona
) -> list[dict[str, str]]:
    """Infer preferences from the persona and create inferred_pending records.

    Returns the list of newly inferred preferences (key/value dicts).
    Skips keys that already have a preference (any source).
    """
    existing_keys: set[str] = set(
        (await session.execute(
            select(Preference.key).where(Preference.persona_id == persona.id)
        )).scalars().all()
    )

    candidates: list[tuple[str, str]] = []

    # 1. Top technologies from skills
    top_skills = (
        await session.execute(
            select(Skill.canonical_name, Skill.confidence)
            .where(Skill.persona_id == persona.id, Skill.deleted_at.is_(None))
            .order_by(Skill.confidence.desc())
            .limit(8)
        )
    ).all()
    if top_skills:
        names = [s[0] for s in top_skills]
        candidates.append(("preferred_technologies", ", ".join(names)))

    # 2. Seniority level from most recent experience
    recent_exp = (
        await session.execute(
            select(Experience)
            .where(Experience.persona_id == persona.id, Experience.deleted_at.is_(None))
            .order_by(Experience.start_date.desc().nulls_last())
            .limit(3)
        )
    ).scalars().all()

    if recent_exp:
        roles = " ".join(e.role or "" for e in recent_exp)
        if _SENIOR_PATTERN.search(roles):
            candidates.append(("seniority_level", "senior"))
        elif _JUNIOR_PATTERN.search(roles):
            candidates.append(("seniority_level", "junior"))
        else:
            candidates.append(("seniority_level", "mid-level"))

    # 3. Work mode from experience descriptions
    all_descs = " ".join(e.description or "" for e in recent_exp) if recent_exp else ""
    if _REMOTE_PATTERN.search(all_descs):
        candidates.append(("work_mode", "remote"))
    elif _HYBRID_PATTERN.search(all_descs):
        candidates.append(("work_mode", "hybrid"))

    # 4. Specialization from experience titles
    if recent_exp:
        titles = " ".join((e.role or "").lower() for e in recent_exp)
        if "backend" in titles:
            candidates.append(("specialization", "backend"))
        elif "frontend" in titles or "ui" in titles:
            candidates.append(("specialization", "frontend"))
        elif "fullstack" in titles or "full stack" in titles or "full-stack" in titles:
            candidates.append(("specialization", "fullstack"))
        elif "devops" in titles or "sre" in titles or "platform" in titles:
            candidates.append(("specialization", "devops / platform"))
        elif "data" in titles or "ml" in titles or "machine learning" in titles:
            candidates.append(("specialization", "data / ML"))

    created: list[dict[str, str]] = []
    for key, value in candidates:
        if key in existing_keys:
            continue
        pref = Preference(
            persona_id=persona.id,
            key=key,
            value=value,
            source=PreferenceSource.inferred_pending,
        )
        session.add(pref)
        existing_keys.add(key)
        created.append({"key": key, "value": value})

    if created:
        await session.flush()
    return created


async def confirm_preference(
    session: AsyncSession, persona: Persona, pref_id: uuid.UUID
) -> Preference:
    pref = await session.get(Preference, pref_id)
    if pref is None or pref.persona_id != persona.id:
        from app.core.errors import NotFoundError
        raise NotFoundError("Preference not found")
    pref.source = PreferenceSource.confirmed
    await session.flush()
    await session.refresh(pref)
    return pref


async def dismiss_preference(
    session: AsyncSession, persona: Persona, pref_id: uuid.UUID
) -> None:
    pref = await session.get(Preference, pref_id)
    if pref is None or pref.persona_id != persona.id:
        from app.core.errors import NotFoundError
        raise NotFoundError("Preference not found")
    await session.delete(pref)
    await session.flush()
