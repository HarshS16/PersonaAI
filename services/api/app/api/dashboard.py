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
