"""Inferred preference endpoints: infer, list pending, confirm, dismiss."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_session
from app.domain.persona import get_or_create_persona
from app.domain.preferences import confirm_preference, dismiss_preference, infer_preferences
from app.models.enums import PreferenceSource
from app.models.persona import Preference
from app.models.user import User
from app.schemas.persona import PreferenceOut

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.post("/infer")
async def infer(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Trigger preference inference from persona data."""
    persona = await get_or_create_persona(session, user.id)
    created = await infer_preferences(session, persona)
    await session.commit()
    return {"inferred": created, "count": len(created)}


@router.get("/pending", response_model=list[PreferenceOut])
async def pending(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[PreferenceOut]:
    """List preferences awaiting user confirmation."""
    persona = await get_or_create_persona(session, user.id)
    rows = (
        await session.execute(
            select(Preference).where(
                Preference.persona_id == persona.id,
                Preference.source == PreferenceSource.inferred_pending,
            )
        )
    ).scalars().all()
    return [PreferenceOut.model_validate(r) for r in rows]


@router.post("/{pref_id}/confirm", response_model=PreferenceOut)
async def confirm(
    pref_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PreferenceOut:
    persona = await get_or_create_persona(session, user.id)
    pref = await confirm_preference(session, persona, pref_id)
    await session.commit()
    return PreferenceOut.model_validate(pref)


@router.delete("/{pref_id}/dismiss", status_code=204)
async def dismiss(
    pref_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    persona = await get_or_create_persona(session, user.id)
    await dismiss_preference(session, persona, pref_id)
    await session.commit()
