"""Agentic job search: search → evaluate → rank → approval → apply (SRD §58).

The agent loop:
  1. User describes what they're looking for (query + optional criteria).
  2. System searches free job boards (simulated in MVP with LLM generation).
  3. Each lead is evaluated against the persona for fit.
  4. Leads are ranked and presented for user approval.
  5. Approved leads get a tailored application generated.

Every external-facing action (applying) requires explicit user confirmation.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import complete_structured, get_llm
from app.ai.llm.base import Message
from app.ai.rag.retrieval import build_context_block, retrieve
from app.core.config import settings
from app.core.errors import AppError, NotFoundError
from app.models.generation import Generation
from app.models.job_search import JobLead, JobSearchTask
from app.models.persona import Persona


class _SearchedJob(BaseModel):
    title: str
    company: str
    location: str | None = None
    description: str
    url: str | None = None


class _SearchResults(BaseModel):
    jobs: list[_SearchedJob] = Field(default_factory=list)


class _FitEvaluation(BaseModel):
    fit_score: float = Field(ge=0, le=1)
    explanation: str
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)


# -----------------------------------------------------------------------
# 1. Create search task
# -----------------------------------------------------------------------


async def create_search(
    session: AsyncSession,
    persona: Persona,
    *,
    query: str,
    criteria: dict[str, Any] | None = None,
) -> JobSearchTask:
    task = JobSearchTask(
        persona_id=persona.id,
        query=query,
        criteria=criteria or {},
        status="pending",
    )
    session.add(task)
    await session.flush()
    return task


# -----------------------------------------------------------------------
# 2. Search for jobs (LLM-powered in MVP)
# -----------------------------------------------------------------------

_SEARCH_SYSTEM = (
    "You are a job search agent. Given the user's search query and their "
    "professional profile, generate realistic job listings that would match. "
    "Return 5–8 jobs as JSON with keys: title, company, location, "
    "description (2-3 sentences), url (null if unknown).\n"
    "Only suggest jobs that are plausible given the candidate's background.\n"
    "Output ONLY the JSON object with a 'jobs' key."
)


async def search_jobs(
    session: AsyncSession,
    persona: Persona,
    task: JobSearchTask,
) -> list[JobLead]:
    ctx = await retrieve(session, persona, task.query)
    context_block = build_context_block(ctx)
    criteria_str = ""
    if task.criteria:
        parts = [f"- {k}: {v}" for k, v in task.criteria.items()]
        criteria_str = "\nPreferences:\n" + "\n".join(parts)

    messages: list[Message] = [
        {"role": "system", "content": _SEARCH_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Search query: {task.query}{criteria_str}\n\n"
                f"Candidate profile:\n{context_block}"
            ),
        },
    ]
    results, _ = await complete_structured(
        _SearchResults, messages,
        model=settings.llm_model_strong, max_tokens=3000,
        purpose="job_search",
    )

    leads: list[JobLead] = []
    for job in results.jobs:
        lead = JobLead(
            task_id=task.id,
            persona_id=persona.id,
            title=job.title,
            company=job.company,
            url=job.url,
            description=job.description,
            location=job.location,
            source_board="ai_search",
        )
        session.add(lead)
        leads.append(lead)

    await session.flush()
    task.status = "searching"
    task.results_count = len(leads)
    await session.flush()
    return leads


# -----------------------------------------------------------------------
# 3. Evaluate each lead against persona
# -----------------------------------------------------------------------

_EVAL_SYSTEM = (
    "You are a job-fit evaluator. Given a job description and the candidate's "
    "professional profile, evaluate how well the candidate fits.\n"
    "Return JSON with keys:\n"
    "- fit_score (0.0 to 1.0)\n"
    "- explanation (1-2 sentences)\n"
    "- matched_skills (list of skills the candidate has)\n"
    "- missing_skills (list of skills they lack)\n"
    "Output ONLY the JSON object."
)


async def evaluate_leads(
    session: AsyncSession,
    persona: Persona,
    task: JobSearchTask,
) -> list[JobLead]:
    leads = (
        await session.execute(
            select(JobLead)
            .where(JobLead.task_id == task.id)
            .order_by(JobLead.created_at)
        )
    ).scalars().all()

    ctx = await retrieve(session, persona, task.query)
    context_block = build_context_block(ctx)

    for lead in leads:
        messages: list[Message] = [
            {"role": "system", "content": _EVAL_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Job: {lead.title} at {lead.company or 'Unknown'}\n"
                    f"Description: {lead.description or 'N/A'}\n\n"
                    f"Candidate profile:\n{context_block}"
                ),
            },
        ]
        evaluation, _ = await complete_structured(
            _FitEvaluation, messages,
            model=settings.llm_model_fast, max_tokens=800,
            purpose="job_eval",
        )
        lead.fit_score = evaluation.fit_score
        lead.fit_explanation = evaluation.explanation
        lead.matched_skills = evaluation.matched_skills
        lead.missing_skills = evaluation.missing_skills

    await session.flush()
    task.status = "evaluated"
    await session.flush()

    ranked = sorted(leads, key=lambda lead: lead.fit_score, reverse=True)
    return list(ranked)


# -----------------------------------------------------------------------
# 4. Approval gate
# -----------------------------------------------------------------------


async def approve_lead(
    session: AsyncSession,
    persona: Persona,
    lead_id: uuid.UUID,
) -> JobLead:
    lead = await session.get(JobLead, lead_id)
    if lead is None or lead.persona_id != persona.id:
        raise NotFoundError("Job lead not found")
    if lead.approval_status not in ("pending", "rejected"):
        raise AppError(
            "Lead already approved or applied",
            code="invalid_state",
        )
    lead.approval_status = "approved"
    await session.flush()
    return lead


async def reject_lead(
    session: AsyncSession,
    persona: Persona,
    lead_id: uuid.UUID,
) -> JobLead:
    lead = await session.get(JobLead, lead_id)
    if lead is None or lead.persona_id != persona.id:
        raise NotFoundError("Job lead not found")
    lead.approval_status = "rejected"
    await session.flush()
    return lead


# -----------------------------------------------------------------------
# 5. Generate application for approved lead
# -----------------------------------------------------------------------


async def generate_application(
    session: AsyncSession,
    persona: Persona,
    lead_id: uuid.UUID,
) -> dict[str, Any]:
    lead = await session.get(JobLead, lead_id)
    if lead is None or lead.persona_id != persona.id:
        raise NotFoundError("Job lead not found")
    if lead.approval_status != "approved":
        raise AppError(
            "Lead must be approved before generating an application",
            code="not_approved",
        )

    ctx = await retrieve(
        session, persona, f"{lead.title} {lead.company or ''}"
    )
    context_block = build_context_block(ctx)
    name = persona.full_name or "the candidate"

    system = (
        f"You are writing a job application for {name}. "
        "Generate a tailored cover letter and key talking points "
        "for this specific role. Ground every claim in the candidate's "
        "actual background — never fabricate experience.\n\n"
        f"Candidate profile:\n{context_block}"
    )
    user_msg = (
        f"Role: {lead.title}\n"
        f"Company: {lead.company or 'Unknown'}\n"
        f"Description: {lead.description or 'N/A'}\n\n"
        "Generate:\n"
        "1. A tailored cover letter (3-4 paragraphs)\n"
        "2. Key talking points (3-5 bullets)\n"
        "3. Questions to ask the interviewer (2-3)"
    )

    llm = get_llm()
    messages: list[Message] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]
    result = await llm.complete(
        messages, model=settings.llm_model_strong,
        max_tokens=2000, temperature=0.5,
        purpose="job_application",
    )

    output = {
        "cover_letter": result.text.strip(),
        "job_title": lead.title,
        "company": lead.company,
        "fit_score": lead.fit_score,
        "matched_skills": lead.matched_skills,
        "missing_skills": lead.missing_skills,
    }

    gen = Generation(
        persona_id=persona.id,
        type="job_application",
        title=f"Application: {lead.title} at {lead.company or 'Unknown'}",
        input={"lead_id": str(lead_id), "job_title": lead.title},
        output=output,
    )
    session.add(gen)
    await session.flush()

    lead.approval_status = "applied"
    lead.application_id = gen.id
    await session.flush()

    return {"id": str(gen.id), **output}


# -----------------------------------------------------------------------
# Queries
# -----------------------------------------------------------------------


async def get_task(
    session: AsyncSession, persona: Persona, task_id: uuid.UUID,
) -> JobSearchTask:
    task = await session.get(JobSearchTask, task_id)
    if task is None or task.persona_id != persona.id:
        raise NotFoundError("Search task not found")
    return task


async def list_tasks(
    session: AsyncSession, persona: Persona,
) -> list[JobSearchTask]:
    rows = (
        await session.execute(
            select(JobSearchTask)
            .where(JobSearchTask.persona_id == persona.id)
            .order_by(JobSearchTask.created_at.desc())
            .limit(20)
        )
    ).scalars().all()
    return list(rows)


async def list_leads(
    session: AsyncSession,
    persona: Persona,
    task_id: uuid.UUID,
) -> list[JobLead]:
    task = await get_task(session, persona, task_id)
    rows = (
        await session.execute(
            select(JobLead)
            .where(JobLead.task_id == task.id)
            .order_by(JobLead.fit_score.desc())
        )
    ).scalars().all()
    return list(rows)
