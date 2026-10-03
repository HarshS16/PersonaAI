"""Research import endpoints: connect Semantic Scholar, arXiv, or ORCID."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import get_session
from app.core.errors import AppError
from app.domain.persona import get_or_create_persona
from app.models.ingestion import Job, Source
from app.models.user import User
from app.schemas.ingestion import JobOut, SourceOut

router = APIRouter(prefix="/sources/research", tags=["research"])

PROVIDERS = {"semantic_scholar", "arxiv", "orcid"}


class ResearchConnectRequest(BaseModel):
    provider: str = Field(default="semantic_scholar")
    query: str = Field(min_length=1, max_length=500,
                       description="Author name or ORCID ID (e.g. 0000-0002-1825-0097)")


class ResearchConnectResponse(BaseModel):
    source: SourceOut
    job: JobOut


@router.post("/connect", response_model=ResearchConnectResponse, status_code=201)
async def research_connect(
    body: ResearchConnectRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ResearchConnectResponse:
    if body.provider not in PROVIDERS:
        raise AppError(
            f"Unknown provider. Choose one of: {', '.join(sorted(PROVIDERS))}",
            code="bad_provider",
        )
    persona = await get_or_create_persona(session, user.id)
    title = f"{body.provider.replace('_', ' ').title()}: {body.query}"
    source = Source(
        persona_id=persona.id, type="research", provider=body.provider, title=title,
        status="processing", stats={"provider": body.provider, "query": body.query},
    )
    session.add(source)
    await session.flush()

    job = Job(persona_id=persona.id, source_id=source.id, type="sync_research", status="queued")
    session.add(job)
    await session.flush()
    await _dispatch(job.id)

    return ResearchConnectResponse(
        source=SourceOut.model_validate(source), job=JobOut.model_validate(job)
    )


async def _dispatch(job_id: uuid.UUID) -> None:
    if settings.environment.lower() == "test":
        return
    from app.workers.tasks import sync_research_task

    sync_research_task.delay(str(job_id))
