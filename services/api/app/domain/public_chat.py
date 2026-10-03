"""Public "Ask <Name> AI" chat — rate-limited, no auth, public facts only.

A visitor asks a question about someone's public persona. The LLM answers
grounded strictly in that persona's public-visibility facts and chunks.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import get_llm
from app.ai.llm.base import Message
from app.core.config import settings
from app.models.enums import Visibility
from app.models.facts import Achievement, Education, Experience, Project, Publication, Skill
from app.models.persona import Persona


async def _public_facts_context(session: AsyncSession, persona: Persona) -> str:
    """Build a grounding context string from public-visibility facts only."""
    parts: list[str] = []

    async def _get(model: Any) -> list[Any]:
        rows = await session.execute(
            select(model).where(
                model.persona_id == persona.id,
                model.deleted_at.is_(None),
                model.visibility == Visibility.public,
            )
        )
        return list(rows.scalars().all())

    skills = await _get(Skill)
    if skills:
        parts.append("Skills: " + ", ".join(s.name for s in skills))

    for exp in await _get(Experience):
        line = f"Experience: {exp.role}"
        if exp.company:
            line += f" at {exp.company}"
        if exp.description:
            line += f" — {exp.description}"
        parts.append(line)

    for proj in await _get(Project):
        line = f"Project: {proj.name}"
        if proj.description:
            line += f" — {proj.description}"
        if proj.technologies:
            line += f" (tech: {', '.join(proj.technologies)})"
        parts.append(line)

    for edu in await _get(Education):
        line = f"Education: {edu.institution}"
        if edu.degree:
            line += f", {edu.degree}"
        parts.append(line)

    for pub in await _get(Publication):
        line = f"Publication: {pub.title}"
        if pub.venue:
            line += f" ({pub.venue})"
        parts.append(line)

    for ach in await _get(Achievement):
        parts.append(f"Achievement: {ach.title}")

    return "\n".join(parts) if parts else "No public information available."


async def public_ask(
    session: AsyncSession, persona: Persona, question: str
) -> dict[str, Any]:
    """Answer a visitor question grounded in public facts only."""
    name = persona.full_name or "this person"
    context = await _public_facts_context(session, persona)

    system = (
        f"You are an AI representing {name}'s public professional profile. "
        f"Answer the visitor's question accurately based ONLY on the following facts. "
        "Do NOT invent or assume anything not stated below. If the information is not "
        "available, say so politely. Be concise (1-3 sentences).\n\n"
        f"Public profile of {name}:\n{context}"
    )
    messages: list[Message] = [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]
    llm = get_llm()
    result = await llm.complete(
        messages, model=settings.llm_model_fast, max_tokens=500, temperature=0.3,
        purpose="public_ask",
    )
    return {"answer": result.text.strip(), "persona_name": name}
