"""Dashboard summary and persona graph endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_session
from app.domain.dashboard import build_graph, build_summary
from app.domain.persona import get_or_create_persona
from app.models.user import User

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
async def dashboard(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    persona = await get_or_create_persona(session, user.id)
    return await build_summary(session, persona)


@router.get("/persona/graph")
async def persona_graph(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    persona = await get_or_create_persona(session, user.id)
    return await build_graph(session, persona)


@router.get("/persona/writing-style")
async def persona_writing_style(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    from sqlalchemy import select

    from app.models.persona import WritingStyle

    persona = await get_or_create_persona(session, user.id)
    row = (
        await session.execute(select(WritingStyle).where(WritingStyle.persona_id == persona.id))
    ).scalar_one_or_none()
    return dict(row.metrics) if row and row.metrics else {}
