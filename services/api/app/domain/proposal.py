"""Freelancer proposal generator (SRD §32, §57).

Given a project description (from Upwork/Toptal/etc.), generates a tailored
proposal grounded in the persona's verified skills, projects, and experience.
The claim validator surfaces any unsupported assertions as warnings.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import get_llm
from app.ai.llm.base import Message
from app.ai.rag.retrieval import build_context_block, retrieve
from app.ai.rag.validation import ClaimStatus, validate_text
from app.ai.writing_style import style_descriptor
from app.core.config import settings
from app.domain.content import _style_hint
from app.models.persona import Persona


def _warnings(text: str, evidence: str) -> list[str]:
    warnings: list[str] = []
    for v in validate_text(text, evidence):
        if v.status == ClaimStatus.reject:
            warnings.append(f"Unsupported: “{v.claim[:120]}” ({v.reason})")
        elif v.status == ClaimStatus.downgrade:
            warnings.append(f"Overclaim: “{v.claim[:120]}” — {v.reason}")
    return warnings[:8]


async def generate_proposal(
    session: AsyncSession,
    persona: Persona,
    *,
    project_description: str,
    platform: str = "upwork",
    tone: str = "professional",
) -> dict[str, Any]:
    ctx = await retrieve(
        session, persona,
        project_description[:2000] or "my professional background",
    )
    context_block = build_context_block(ctx)
    name = persona.full_name or "the freelancer"
    style = await _style_hint(session, persona)

    platform_hint = {
        "upwork": "an Upwork freelancer proposal (concise opening hook, relevant experience, clear deliverables, timeline mention)",
        "toptal": "a Toptal application-style proposal (technical depth, past results, structured approach)",
        "fiverr": "a Fiverr gig proposal (friendly, outcome-focused, quick turnaround emphasis)",
        "generic": "a freelance project proposal (professional, clear scope and approach)",
    }.get(platform.lower(), "a freelance project proposal")

    system = (
        f"You are writing {platform_hint} as {name}, in a {tone} tone.\n"
        "Structure: 1) Opening hook (why you're a great fit), "
        "2) Relevant experience/projects (specific, grounded), "
        "3) Proposed approach (brief), "
        "4) Timeline/availability.\n"
        "Ground EVERY claim in the background below — do NOT invent experience, "
        f"metrics, clients, or projects. Write in first person. {style}\n\n"
        f"Background:\n{context_block}"
    )

    llm = get_llm()
    messages: list[Message] = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Project description:\n{project_description[:4000]}"},
    ]
    result = await llm.complete(
        messages, model=settings.llm_model_strong, max_tokens=1200,
        temperature=0.5, purpose="generate_proposal",
    )
    content = result.text.strip()

    return {
        "content": content,
        "warnings": _warnings(content, context_block),
        "platform": platform,
        "tone": tone,
    }
