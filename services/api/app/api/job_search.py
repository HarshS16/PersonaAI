"""Agentic job search API (SRD §58).

Flow: create search → run search → evaluate → approve/reject → apply.
Every action with external consequences requires explicit user approval.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_session
from app.domain import job_search as svc
from app.domain.persona import get_or_create_persona
from app.models.persona import Persona
from app.models.user import User

router = APIRouter(prefix="/agent/jobs", tags=["job-search"])


class SearchRequest(BaseModel):
    query: str = Field(min_length=5, max_length=2000)
    criteria: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional filters: location, remote, salary_min, "
            "experience_level, etc."
        ),
    )


class LeadOut(BaseModel):
    id: str
    title: str
    company: str | None
    url: str | None
    location: str | None
    description: str | None
    fit_score: float
    fit_explanation: str | None
    matched_skills: list[str]
    missing_skills: list[str]
    approval_status: str


class TaskOut(BaseModel):
    id: str
    query: str
    criteria: dict[str, Any]
    status: str
    results_count: int
    created_at: str


async def _persona(
    session: AsyncSession, user: User,
) -> Persona:
    return await get_or_create_persona(session, user.id)


def _task_out(t: Any) -> TaskOut:
    return TaskOut(
        id=str(t.id),
        query=t.query,
        criteria=t.criteria,
        status=t.status,
        results_count=t.results_count,
        created_at=t.created_at.isoformat(),
    )


def _lead_out(lead: Any) -> LeadOut:
    return LeadOut(
        id=str(lead.id),
        title=lead.title,
        company=lead.company,
        url=lead.url,
        location=lead.location,
        description=lead.description,
        fit_score=lead.fit_score,
        fit_explanation=lead.fit_explanation,
        matched_skills=lead.matched_skills,
        missing_skills=lead.missing_skills,
        approval_status=lead.approval_status,
    )


@router.post("/search", status_code=201)
async def create_search(
    body: SearchRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Start an agentic job search. The system will find, evaluate, and
    rank opportunities — then wait for your approval before acting."""
    persona = await _persona(session, user)
    task = await svc.create_search(
        session, persona,
        query=body.query, criteria=body.criteria,
    )
    await svc.search_jobs(session, persona, task)
    ranked = await svc.evaluate_leads(session, persona, task)
    return {
        "task": _task_out(task).model_dump(),
        "leads": [_lead_out(lead).model_dump() for lead in ranked],
    }


@router.get("/tasks")
async def list_tasks(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    persona = await _persona(session, user)
    tasks = await svc.list_tasks(session, persona)
    return [_task_out(t).model_dump() for t in tasks]


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    persona = await _persona(session, user)
    task = await svc.get_task(session, persona, task_id)
    return _task_out(task).model_dump()


@router.get("/tasks/{task_id}/leads")
async def list_leads(
    task_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    persona = await _persona(session, user)
    leads = await svc.list_leads(session, persona, task_id)
    return [_lead_out(lead).model_dump() for lead in leads]


@router.post("/leads/{lead_id}/approve")
async def approve_lead(
    lead_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LeadOut:
    persona = await _persona(session, user)
    lead = await svc.approve_lead(session, persona, lead_id)
    return _lead_out(lead)


@router.post("/leads/{lead_id}/reject")
async def reject_lead(
    lead_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LeadOut:
    persona = await _persona(session, user)
    lead = await svc.reject_lead(session, persona, lead_id)
    return _lead_out(lead)


@router.post("/leads/{lead_id}/apply")
async def apply_to_lead(
    lead_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Generate a tailored application for an approved lead.
    The lead must be approved first — this is the confirmation gate."""
    persona = await _persona(session, user)
    return await svc.generate_application(session, persona, lead_id)
