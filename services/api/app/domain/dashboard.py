"""Dashboard summary and persona graph assembly."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.merge import _canonical_skill
from app.domain.persona import compute_completeness
from app.models.evidence import Evidence
from app.models.facts import Education, Experience, Project, Skill
from app.models.generation import Generation
from app.models.ingestion import Source
from app.models.persona import Persona


async def _active(session: AsyncSession, model: Any, persona_id: Any) -> list[Any]:
    rows = await session.execute(
        select(model).where(model.persona_id == persona_id, model.deleted_at.is_(None))
    )
    return list(rows.scalars().all())


async def build_summary(session: AsyncSession, persona: Persona) -> dict[str, Any]:
    await compute_completeness(session, persona)

    skills = await _active(session, Skill, persona.id)
    projects = await _active(session, Project, persona.id)
    experiences = await _active(session, Experience, persona.id)
    education = await _active(session, Education, persona.id)

    top_skills = sorted(
        skills, key=lambda s: (s.confidence, s.evidence_count), reverse=True
    )[:8]

    timeline = sorted(
        experiences,
        key=lambda e: (e.is_current, e.start_date or datetime.min.date()),
        reverse=True,
    )

    sources = await _active_sources(session, persona.id)

    return {
        "greeting_name": persona.full_name,
        "completeness": persona.completeness,
        "counts": {
            "skills": len(skills),
            "projects": len(projects),
            "experiences": len(experiences),
            "education": len(education),
            "sources": len(sources),
        },
        "top_skills": [
            {"id": str(s.id), "name": s.name, "confidence": s.confidence,
             "evidence_count": s.evidence_count}
            for s in top_skills
        ],
        "projects": [
            {"id": str(p.id), "name": p.name, "technologies": p.technologies}
            for p in projects[:6]
        ],
        "timeline": [
            {
                "id": str(e.id),
                "role": e.role,
                "company": e.company,
                "start_date": e.start_date.isoformat() if e.start_date else None,
                "end_date": e.end_date.isoformat() if e.end_date else None,
                "is_current": e.is_current,
            }
            for e in timeline
        ],
        "sources": [
            {"id": str(s.id), "type": s.type, "title": s.title, "status": s.status,
             "last_synced": s.last_synced.isoformat() if s.last_synced else None}
            for s in sources
        ],
        "recent_activity": await _recent_activity(session, persona.id),
        "has_sources": len(sources) > 0,
    }


async def _active_sources(session: AsyncSession, persona_id: Any) -> list[Source]:
    rows = await session.execute(
        select(Source).where(Source.persona_id == persona_id).order_by(Source.created_at.desc())
    )
    return list(rows.scalars().all())


async def _recent_activity(session: AsyncSession, persona_id: Any) -> list[dict[str, Any]]:
    """Derive a recent-updates feed from synced sources and generations."""
    events: list[dict[str, Any]] = []

    srcs = await session.execute(
        select(Source)
        .where(Source.persona_id == persona_id, Source.last_synced.is_not(None))
        .order_by(Source.last_synced.desc())
        .limit(5)
    )
    for s in srcs.scalars().all():
        created = (s.stats or {}).get("created", {})
        total = sum(created.values()) if isinstance(created, dict) else 0
        events.append(
            {
                "kind": "source_synced",
                "text": f"{s.title or s.type} synced — {total} facts",
                "at": s.last_synced.isoformat() if s.last_synced else None,
            }
        )

    gens = await session.execute(
        select(Generation)
        .where(Generation.persona_id == persona_id)
        .order_by(Generation.created_at.desc())
        .limit(5)
    )
    for g in gens.scalars().all():
        events.append(
            {
                "kind": g.type,
                "text": f"Generated {g.type.replace('_', ' ')}"
                + (f": {g.title}" if g.title else ""),
                "at": g.created_at.isoformat(),
            }
        )

    events.sort(key=lambda e: e["at"] or "", reverse=True)
    return events[:8]


async def build_graph(session: AsyncSession, persona: Persona) -> dict[str, Any]:
    """Nodes and edges for the Persona Explorer (SRD §53)."""
    skills = await _active(session, Skill, persona.id)
    projects = await _active(session, Project, persona.id)
    experiences = await _active(session, Experience, persona.id)
    education = await _active(session, Education, persona.id)

    skill_by_canon = {s.canonical_name: s for s in skills}

    nodes: list[dict[str, Any]] = [
        {
            "id": "persona",
            "type": "persona",
            "label": persona.full_name or persona.headline or "You",
        }
    ]
    edges: list[dict[str, Any]] = []

    for s in skills:
        nid = f"skill:{s.id}"
        nodes.append({
            "id": nid, "type": "skill", "label": s.name,
            "confidence": s.confidence, "evidence_count": s.evidence_count,
        })
        edges.append({"id": f"e-{nid}", "source": "persona", "target": nid, "label": "skilled in"})

    for p in projects:
        nid = f"project:{p.id}"
        nodes.append({"id": nid, "type": "project", "label": p.name, "confidence": p.confidence})
        edges.append({"id": f"e-{nid}", "source": "persona", "target": nid, "label": "built"})
        for tech in p.technologies:
            sk = skill_by_canon.get(_canonical_skill(tech))
            if sk is not None:
                edges.append({
                    "id": f"e-{nid}-skill:{sk.id}",
                    "source": nid, "target": f"skill:{sk.id}", "label": "uses",
                })

    for e in experiences:
        nid = f"experience:{e.id}"
        label = f"{e.role}" + (f" · {e.company}" if e.company else "")
        nodes.append({"id": nid, "type": "experience", "label": label, "confidence": e.confidence})
        edges.append({"id": f"e-{nid}", "source": "persona", "target": nid, "label": "worked"})

    for ed in education:
        nid = f"education:{ed.id}"
        nodes.append({"id": nid, "type": "education", "label": ed.institution})
        edges.append({"id": f"e-{nid}", "source": "persona", "target": nid, "label": "studied"})

    # Total evidence for the header stat.
    ev_count = await session.execute(
        select(func.count()).select_from(Evidence).where(Evidence.persona_id == persona.id)
    )

    return {"nodes": nodes, "edges": edges, "evidence_total": int(ev_count.scalar_one())}
