"""GitHub connector endpoints: status, connect, re-sync."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import get_session
from app.core.errors import AppError, NotFoundError
from app.domain.persona import get_or_create_persona
from app.models.ingestion import Job, Source
from app.models.user import OAuthAccount, OAuthProvider, User
from app.schemas.ingestion import JobOut, SourceOut

router = APIRouter(prefix="/sources/github", tags=["github"])


class GitHubConnectRequest(BaseModel):
    username: str | None = None


class GitHubStatus(BaseModel):
    oauth_connected: bool
    username: str | None
    source_id: uuid.UUID | None


class GitHubConnectResponse(BaseModel):
    source: SourceOut
    job: JobOut


async def _github_account(session: AsyncSession, user: User) -> OAuthAccount | None:
    result = await session.execute(
        select(OAuthAccount).where(
            OAuthAccount.user_id == user.id, OAuthAccount.provider == OAuthProvider.github
        )
    )
    return result.scalar_one_or_none()


@router.get("/status", response_model=GitHubStatus)
async def github_status(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GitHubStatus:
    persona = await get_or_create_persona(session, user.id)
    account = await _github_account(session, user)
    existing = await session.execute(
        select(Source).where(Source.persona_id == persona.id, Source.type == "github")
    )
    source = existing.scalar_one_or_none()
    return GitHubStatus(
        oauth_connected=account is not None,
        username=account.provider_username if account else None,
        source_id=source.id if source else None,
    )


@router.post("/connect", response_model=GitHubConnectResponse, status_code=201)
async def github_connect(
    body: GitHubConnectRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GitHubConnectResponse:
    persona = await get_or_create_persona(session, user.id)
    account = await _github_account(session, user)

    username = body.username or (account.provider_username if account else None)
    if account is None and not username:
        raise AppError(
            "Connect GitHub by logging in with GitHub, or provide a public username.",
            code="github_not_connected",
            status_code=400,
        )

    # One GitHub source per persona: reuse if present.
    existing = await session.execute(
        select(Source).where(Source.persona_id == persona.id, Source.type == "github")
    )
    source = existing.scalar_one_or_none()
    if source is None:
        source = Source(persona_id=persona.id, type="github", provider="github", title="GitHub")
        session.add(source)
    source.status = "processing"
    source.error = None
    stats = dict(source.stats or {})
    if username:
        stats["username"] = username
    source.stats = stats
    await session.flush()

    job = Job(persona_id=persona.id, source_id=source.id, type="sync_github", status="queued")
    session.add(job)
    await session.flush()

    await _dispatch(job.id)

    return GitHubConnectResponse(
        source=SourceOut.model_validate(source), job=JobOut.model_validate(job)
    )


@router.post("/{source_id}/sync", response_model=JobOut, status_code=201)
async def github_sync(
    source_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> JobOut:
    persona = await get_or_create_persona(session, user.id)
    source = await session.get(Source, source_id)
    if source is None or source.persona_id != persona.id or source.type != "github":
        raise NotFoundError("GitHub source not found")
    source.status = "processing"
    job = Job(persona_id=persona.id, source_id=source.id, type="sync_github", status="queued")
    session.add(job)
    await session.flush()
    await _dispatch(job.id)
    return JobOut.model_validate(job)


async def _dispatch(job_id) -> None:  # type: ignore[no-untyped-def]
    if settings.environment.lower() == "test":
        return
    from app.workers.tasks import sync_github_task

    sync_github_task.delay(str(job_id))
