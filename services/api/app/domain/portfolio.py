"""Portfolio generation (SRD §30).

Assembles the persona into a portfolio — About / Skills / Experience / Projects /
Research / Achievements / Contact — and renders a self-contained, themeable HTML
page the user can host anywhere. The About blurb is written by the LLM but
grounded in the persona; everything else is the user's own structured facts.
"""

from __future__ import annotations

import html
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import get_llm
from app.ai.llm.base import Message
from app.core.config import settings
from app.domain.dashboard import _active
from app.models.enums import Visibility
from app.models.facts import (
    Achievement,
    Education,
    Experience,
    Project,
    Publication,
    Skill,
)
from app.models.persona import Persona


async def _about(persona: Persona, skills: list[str], top_roles: list[str]) -> str:
    system = (
        f"Write a 2-3 sentence professional 'About' blurb for {persona.full_name or 'this person'}"
        f" ({persona.headline or 'professional'}). Ground it only in these facts: "
        f"skills: {', '.join(skills[:10])}; recent roles: {', '.join(top_roles[:3])}. "
        "First person. No invented facts. Return only the blurb."
    )
    messages: list[Message] = [
        {"role": "system", "content": system},
        {"role": "user", "content": "Write the About section."},
    ]
    result = await get_llm().complete(
        messages, model=settings.llm_model_strong, max_tokens=300, temperature=0.5,
        purpose="portfolio_about",
    )
    return result.text.strip()


async def generate_portfolio(
    session: AsyncSession, persona: Persona, *, public_only: bool = False
) -> dict[str, Any]:
    def _filter(rows: list[Any]) -> list[Any]:
        if not public_only:
            return rows
        return [
            r for r in rows
            if getattr(r, "visibility", Visibility.private) == Visibility.public
        ]

    skills = _filter(await _active(session, Skill, persona.id))
    experiences = _filter(await _active(session, Experience, persona.id))
    projects = _filter(await _active(session, Project, persona.id))
    education = _filter(await _active(session, Education, persona.id))
    publications = _filter(await _active(session, Publication, persona.id))
    achievements = _filter(await _active(session, Achievement, persona.id))

    skill_names = [s.name for s in skills]
    about = await _about(persona, skill_names, [e.role for e in experiences])

    portfolio = {
        "name": persona.full_name,
        "headline": persona.headline,
        "about": about,
        "contact": persona.links,
        "skills": skill_names,
        "experience": [
            {"role": e.role, "company": e.company, "description": e.description,
             "start_date": e.start_date.isoformat() if e.start_date else None,
             "end_date": e.end_date.isoformat() if e.end_date else None}
            for e in experiences
        ],
        "projects": [
            {"name": p.name, "description": p.description, "technologies": p.technologies,
             "url": p.repository_url or p.url}
            for p in projects
        ],
        "research": [
            {"title": pb.title, "venue": pb.venue, "year": pb.year, "url": pb.url}
            for pb in publications
        ],
        "education": [
            {"institution": ed.institution, "degree": ed.degree,
             "field_of_study": ed.field_of_study}
            for ed in education
        ],
        "achievements": [{"title": a.title, "description": a.description} for a in achievements],
    }
    return {"portfolio": portfolio, "html": _render_html(portfolio)}


def _render_html(p: dict[str, Any]) -> str:
    e = html.escape

    def section(title: str, body: str) -> str:
        return f'<section><h2>{e(title)}</h2>{body}</section>' if body else ""

    skills = "".join(f"<span class=chip>{e(s)}</span>" for s in p["skills"])
    experience = "".join(
        f'<div class=item><h3>{e(x["role"])}{" · " + e(x["company"]) if x["company"] else ""}</h3>'
        f'<p>{e(x["description"] or "")}</p></div>'
        for x in p["experience"]
    )
    projects = "".join(
        f'<div class=item><h3>{e(x["name"])}</h3><p>{e(x["description"] or "")}</p>'
        f'<p class=tech>{e(", ".join(x["technologies"]))}</p>'
        + (f'<a href="{e(x["url"])}">{e(x["url"])}</a>' if x["url"] else "")
        + "</div>"
        for x in p["projects"]
    )
    research = "".join(
        f'<div class=item><h3>{e(x["title"])}</h3>'
        f'<p>{e(x["venue"] or "")}{" · " + str(x["year"]) if x["year"] else ""}</p></div>'
        for x in p["research"]
    )
    education = "".join(
        f'<div class=item><h3>{e(x["institution"])}</h3>'
        f'<p>{e(" ".join(filter(None, [x["degree"], x["field_of_study"]])))}</p></div>'
        for x in p["education"]
    )
    achievements = "".join(f"<li>{e(x['title'])}</li>" for x in p["achievements"])
    contact = "".join(
        f'<a href="{e(str(v))}">{e(str(k))}</a>' for k, v in (p["contact"] or {}).items()
    )

    return f"""<!doctype html>
<html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width, initial-scale=1">
<title>{e(p["name"] or "Portfolio")}</title>
<style>
:root{{--fg:#0f172a;--muted:#64748b;--bg:#fff;--accent:#6366f1;--chip:#eef2ff}}
@media (prefers-color-scheme:dark){{:root{{--fg:#e2e8f0;--muted:#94a3b8;--bg:#0b1120;--chip:#1e293b}}}}
*{{box-sizing:border-box}}
body{{margin:0;font:16px/1.6 system-ui,sans-serif;color:var(--fg);background:var(--bg)}}
main{{max-width:760px;margin:0 auto;padding:48px 20px}}
header h1{{margin:0;font-size:2rem}}
header p{{color:var(--muted);margin:.25rem 0 1rem}}
h2{{font-size:1.1rem;border-bottom:1px solid var(--chip);padding-bottom:.3rem;margin-top:2.2rem}}
.item{{margin:.9rem 0}} .item h3{{margin:0;font-size:1rem}} .item p{{margin:.2rem 0;color:var(--muted)}}
.tech{{font-size:.85rem}} .chip{{display:inline-block;background:var(--chip);border-radius:999px;padding:.2rem .7rem;margin:.15rem;font-size:.85rem}}
a{{color:var(--accent)}} .contact a{{margin-right:1rem}}
</style></head>
<body><main>
<header><h1>{e(p["name"] or "Your Name")}</h1><p>{e(p["headline"] or "")}</p>
<div class=contact>{contact}</div></header>
{section("About", f"<p>{e(p['about'])}</p>") if p["about"] else ""}
{section("Skills", f"<div>{skills}</div>") if skills else ""}
{section("Experience", experience)}
{section("Projects", projects)}
{section("Research", research)}
{section("Education", education)}
{section("Achievements", f"<ul>{achievements}</ul>") if achievements else ""}
</main></body></html>"""
