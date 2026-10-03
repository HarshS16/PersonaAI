"""Career tools (SRD §24–28): JD analysis, gap analysis, resume generation and
interview preparation — all grounded in the persona and gated by the claim
validator so nothing unsupported is asserted.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.extraction import JDAnalysis
from app.ai.llm import complete_structured
from app.ai.llm.base import Message
from app.ai.rag.validation import ClaimStatus, validate_text
from app.core.config import settings
from app.domain.merge import _canonical_skill
from app.models.evidence import Evidence
from app.models.facts import Education, Experience, Project, Skill
from app.models.persona import Persona

# ---------------------------------------------------------------------------
# JD analysis
# ---------------------------------------------------------------------------

_JD_SYSTEM = """Extract the structured requirements from this job description.
Return JSON with keys: title, required_skills (list), preferred_skills (list),
technologies (list), responsibilities (list), experience_years (int or null),
education (string or null), domain (string or null). Output ONLY JSON."""


async def analyze_jd(jd_text: str) -> JDAnalysis:
    messages: list[Message] = [
        {"role": "system", "content": _JD_SYSTEM},
        {"role": "user", "content": f"Job description:\n\n{jd_text[:12000]}"},
    ]
    analysis, _ = await complete_structured(
        JDAnalysis, messages, model=settings.llm_model_fast, max_tokens=3000, purpose="analyze_jd"
    )
    return analysis


# ---------------------------------------------------------------------------
# Gap / matching
# ---------------------------------------------------------------------------

Status = str  # "strong" | "partial" | "none"


@dataclass
class RequirementMatch:
    requirement: str
    kind: str  # required | preferred
    status: Status
    evidence: list[str] = field(default_factory=list)


async def _evidence_quotes(session: AsyncSession, entity_id: uuid.UUID) -> list[str]:
    rows = (
        await session.execute(
            select(Evidence.content).where(Evidence.entity_id == entity_id).limit(3)
        )
    ).scalars().all()
    return [c for c in rows if c]


async def match_jd(
    session: AsyncSession, persona: Persona, jd: JDAnalysis
) -> list[RequirementMatch]:
    skill_rows = (
        await session.execute(
            select(Skill).where(Skill.persona_id == persona.id, Skill.deleted_at.is_(None))
        )
    ).scalars().all()
    by_canon = {s.canonical_name: s for s in skill_rows}

    # Terms mentioned in projects/experience (for partial credit).
    proj_rows = (
        await session.execute(
            select(Project).where(Project.persona_id == persona.id, Project.deleted_at.is_(None))
        )
    ).scalars().all()
    exp_rows = (
        await session.execute(
            select(Experience).where(
                Experience.persona_id == persona.id, Experience.deleted_at.is_(None)
            )
        )
    ).scalars().all()
    mentioned = " ".join(
        [f"{p.name} {p.description or ''} {' '.join(p.technologies)}" for p in proj_rows]
        + [f"{e.role} {e.description or ''}" for e in exp_rows]
    ).lower()

    matches: list[RequirementMatch] = []
    seen: set[str] = set()
    for kind, items in (("required", jd.required_skills), ("preferred", jd.preferred_skills)):
        for item in items:
            canon = _canonical_skill(item)
            if canon in seen:
                continue
            seen.add(canon)
            sk = by_canon.get(canon)
            evidence: list[str] = []
            if sk is not None:
                evidence = await _evidence_quotes(session, sk.id)
                # A named skill backed by a source (resume/GitHub, weight ~0.5+)
                # or multiple sources is strongly supported (SRD §27).
                strong = sk.confidence >= 0.5 or sk.evidence_count >= 2
                status = "strong" if strong else "partial"
            elif canon in mentioned:
                status = "partial"
            else:
                status = "none"
            matches.append(RequirementMatch(item, kind, status, evidence))
    return matches


def summarize_gap(matches: list[RequirementMatch]) -> dict[str, list[str]]:
    return {
        "strongly_supported": [m.requirement for m in matches if m.status == "strong"],
        "partially_supported": [m.requirement for m in matches if m.status == "partial"],
        "not_demonstrated": [m.requirement for m in matches if m.status == "none"],
    }


# ---------------------------------------------------------------------------
# Resume generation
# ---------------------------------------------------------------------------


async def generate_resume(
    session: AsyncSession, persona: Persona, jd_text: str, *, target_role: str | None = None
) -> dict[str, Any]:
    jd = await analyze_jd(jd_text)
    matches = await match_jd(session, persona, jd)
    gap = summarize_gap(matches)

    jd_techs = {_canonical_skill(t) for t in (jd.technologies + jd.required_skills)}

    # Skills: matched ones, strong first.
    matched_skills = [m.requirement for m in matches if m.status in ("strong", "partial")]

    # Experience with validated bullets + evidence.
    exp_rows = (
        await session.execute(
            select(Experience)
            .where(Experience.persona_id == persona.id, Experience.deleted_at.is_(None))
            .order_by(Experience.is_current.desc(), Experience.created_at.desc())
        )
    ).scalars().all()
    experiences = []
    for e in exp_rows:
        # Evidence for a bullet is the fact's description, structured fields, and
        # source quotes — NOT the free-text highlights themselves, so a highlight
        # that adds unsupported specifics (e.g. a fabricated headcount) is caught.
        ev_text = " ".join(
            [e.role, e.company or "", e.description or "", *(await _evidence_quotes(session, e.id))]
        )
        raw_bullets = e.highlights or ([e.description] if e.description else [])
        bullets = _validated_bullets(raw_bullets, ev_text)
        experiences.append(
            {
                "role": e.role,
                "company": e.company,
                "start_date": e.start_date.isoformat() if e.start_date else None,
                "end_date": e.end_date.isoformat() if e.end_date else None,
                "bullets": bullets,
                "evidence": await _evidence_quotes(session, e.id),
            }
        )

    # Projects: prefer those overlapping the JD's tech.
    proj_rows = (
        await session.execute(
            select(Project).where(Project.persona_id == persona.id, Project.deleted_at.is_(None))
        )
    ).scalars().all()

    def _relevance(p: Project) -> int:
        return len({_canonical_skill(t) for t in p.technologies} & jd_techs)

    projects = []
    for p in sorted(proj_rows, key=_relevance, reverse=True)[:5]:
        ev_text = " ".join(
            [p.name, " ".join(p.technologies), *(await _evidence_quotes(session, p.id))]
        )
        bullets = _validated_bullets([p.description] if p.description else [], ev_text)
        projects.append(
            {
                "name": p.name,
                "technologies": p.technologies,
                "bullets": bullets,
                "url": p.repository_url or p.url,
                "evidence": await _evidence_quotes(session, p.id),
            }
        )

    education = [
        {"institution": ed.institution, "degree": ed.degree, "field_of_study": ed.field_of_study}
        for ed in (
            await session.execute(
                select(Education).where(
                    Education.persona_id == persona.id, Education.deleted_at.is_(None)
                )
            )
        ).scalars().all()
    ]

    headline = target_role or persona.headline or "Professional"
    summary = _summary(persona, headline, matched_skills)

    resume = {
        "name": persona.full_name,
        "headline": headline,
        "summary": summary,
        "skills": matched_skills,
        "experience": experiences,
        "projects": projects,
        "education": education,
    }

    # ATS: how much of the JD's tech is covered by the resume's skills.
    resume_skill_canons = {_canonical_skill(s) for s in matched_skills}
    covered = jd_techs & resume_skill_canons if jd_techs else set()
    ats = {
        "keyword_coverage": round(len(covered) / len(jd_techs), 3) if jd_techs else 1.0,
        "covered": sorted(covered),
        "missing": sorted(jd_techs - resume_skill_canons),
    }

    return {
        "resume": resume,
        "markdown": _render_markdown(resume),
        "jd_analysis": jd.model_dump(),
        "matched_requirements": [m.requirement for m in matches if m.status != "none"],
        "missing_requirements": gap["not_demonstrated"],
        "gap": gap,
        "ats": ats,
    }


def _validated_bullets(raw: list[str], evidence_text: str) -> list[dict[str, Any]]:
    """Keep only evidence-supported bullets; softened where leadership is unbacked."""
    out: list[dict[str, Any]] = []
    for bullet in raw:
        if not bullet:
            continue
        verdicts = validate_text(bullet, evidence_text)
        for v in verdicts:
            if v.status == ClaimStatus.allow:
                out.append({"text": v.claim, "validated": True})
            elif v.status == ClaimStatus.downgrade and v.suggestion:
                out.append({"text": v.suggestion, "validated": True, "softened": True})
            # rejected bullets are dropped
    return out


def _summary(persona: Persona, headline: str, skills: list[str]) -> str:
    top = ", ".join(skills[:5])
    base = f"{headline}"
    if top:
        base += f" with demonstrated experience in {top}"
    return base + "."


def resume_to_html(resume: dict[str, Any]) -> str:
    """Render a resume as a self-contained HTML page suitable for PDF export."""
    import html

    e = html.escape
    name = e(resume.get("name") or "Resume")
    headline = e(resume.get("headline", ""))
    summary = e(resume.get("summary", ""))

    skills_html = ", ".join(e(s) for s in resume.get("skills", []))
    exp_html = ""
    for ex in resume.get("experience", []):
        dates = " – ".join(filter(None, [ex.get("start_date"), ex.get("end_date") or "Present"]))
        company = f" · {e(ex['company'])}" if ex.get("company") else ""
        bullets = "".join(f"<li>{e(b['text'])}</li>" for b in ex.get("bullets", []))
        exp_html += f"<div class=entry><h3>{e(ex['role'])}{company}</h3>"
        exp_html += f"<div class=dates>{e(dates)}</div><ul>{bullets}</ul></div>"

    proj_html = ""
    for p in resume.get("projects", []):
        tech = f" ({', '.join(e(t) for t in p.get('technologies', []))})" if p.get("technologies") else ""
        bullets = "".join(f"<li>{e(b['text'])}</li>" for b in p.get("bullets", []))
        proj_html += f"<div class=entry><h3>{e(p['name'])}{tech}</h3><ul>{bullets}</ul></div>"

    edu_html = ""
    for ed in resume.get("education", []):
        parts = filter(None, [ed.get("degree"), ed.get("field_of_study"), ed.get("institution")])
        edu_html += f"<li>{', '.join(e(p) for p in parts)}</li>"

    return f"""<!doctype html>
<html lang=en><head><meta charset=utf-8>
<title>{name} — Resume</title>
<style>
@page {{ size: A4; margin: 1.5cm; }}
body {{ font: 11pt/1.5 system-ui, sans-serif; color: #1a1a1a; margin: 0; padding: 20px; }}
h1 {{ font-size: 20pt; margin: 0; }} h2 {{ font-size: 12pt; border-bottom: 1px solid #ccc;
padding-bottom: 3px; margin-top: 14px; }} h3 {{ font-size: 11pt; margin: 0; }}
.headline {{ color: #555; margin: 2px 0 8px; }} .dates {{ color: #777; font-size: 10pt; }}
.entry {{ margin: 8px 0; }} ul {{ margin: 2px 0; padding-left: 18px; }}
li {{ margin: 1px 0; }} .skills {{ margin: 4px 0; }}
</style></head><body>
<h1>{name}</h1>
<div class=headline>{headline}</div>
{"<p>" + summary + "</p>" if summary else ""}
{"<h2>Skills</h2><div class=skills>" + skills_html + "</div>" if skills_html else ""}
{"<h2>Experience</h2>" + exp_html if exp_html else ""}
{"<h2>Projects</h2>" + proj_html if proj_html else ""}
{"<h2>Education</h2><ul>" + edu_html + "</ul>" if edu_html else ""}
</body></html>"""


def _render_markdown(resume: dict[str, Any]) -> str:
    lines = [f"# {resume.get('name') or 'Resume'}", f"**{resume['headline']}**", ""]
    if resume.get("summary"):
        lines += [resume["summary"], ""]
    if resume["skills"]:
        lines += ["## Skills", ", ".join(resume["skills"]), ""]
    if resume["experience"]:
        lines += ["## Experience"]
        for e in resume["experience"]:
            dates = " – ".join(filter(None, [e.get("start_date"), e.get("end_date") or "Present"]))
            company = f" · {e['company']}" if e["company"] else ""
            lines.append(f"### {e['role']}{company}  {dates}")
            for b in e["bullets"]:
                lines.append(f"- {b['text']}")
            lines.append("")
    if resume["projects"]:
        lines += ["## Projects"]
        for p in resume["projects"]:
            tech = f" ({', '.join(p['technologies'])})" if p["technologies"] else ""
            lines.append(f"### {p['name']}{tech}")
            for b in p["bullets"]:
                lines.append(f"- {b['text']}")
            lines.append("")
    if resume["education"]:
        lines += ["## Education"]
        for ed in resume["education"]:
            parts = filter(None, [ed["degree"], ed["field_of_study"], ed["institution"]])
            lines.append(f"- {', '.join(parts)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Interview preparation
# ---------------------------------------------------------------------------

INTERVIEW_MODES = {"technical", "hr", "project", "system_design", "behavioral"}


async def generate_interview(
    session: AsyncSession, persona: Persona, *, mode: str, jd_text: str | None = None
) -> list[dict[str, str]]:
    skills = (
        await session.execute(
            select(Skill)
            .where(Skill.persona_id == persona.id, Skill.deleted_at.is_(None))
            .order_by(Skill.confidence.desc())
            .limit(8)
        )
    ).scalars().all()
    projects = (
        await session.execute(
            select(Project)
            .where(Project.persona_id == persona.id, Project.deleted_at.is_(None))
            .limit(5)
        )
    ).scalars().all()

    skill_names = [s.name for s in skills]
    questions: list[dict[str, str]] = []

    if mode == "technical":
        for s in skill_names[:5]:
            questions.append({"question": f"Can you describe a problem you solved using {s}?",
                              "focus": s})
    elif mode == "project":
        for p in projects:
            tech = ", ".join(p.technologies) if p.technologies else "the stack you chose"
            questions.append({"question": f"Walk me through {p.name}. Why did you use {tech}?",
                              "focus": p.name})
    elif mode == "system_design":
        techs = sorted({t for p in projects for t in p.technologies})[:4] or skill_names[:4]
        for t in techs:
            questions.append({"question": f"Design a scalable system that relies on {t}.",
                              "focus": t})
    elif mode == "hr":
        questions = [
            {"question": q, "focus": "hr"}
            for q in (
                "Why are you interested in this role?",
                "What are your salary expectations?",
                "Where do you see yourself in three years?",
                "Why are you leaving your current role?",
            )
        ]
    else:  # behavioral
        questions = [
            {"question": q, "focus": "behavioral"}
            for q in (
                "Tell me about a time you overcame a significant technical challenge.",
                "Describe a disagreement with a teammate and how you resolved it.",
                "Give an example of a project that did not go as planned.",
                "How do you prioritize when everything feels urgent?",
            )
        ]

    # Probe weak areas when a JD is provided.
    if jd_text:
        jd = await analyze_jd(jd_text)
        matches = await match_jd(session, persona, jd)
        weak = [m.requirement for m in matches if m.status == "none"][:3]
        for w in weak:
            questions.append(
                {"question": f"This role mentions {w}. How would you get up to speed on it?",
                 "focus": f"gap:{w}"}
            )

    return questions
