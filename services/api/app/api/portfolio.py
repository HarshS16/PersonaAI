"""Portfolio generation endpoint (SRD §30)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_session
from app.domain.persona import get_or_create_persona
from app.domain.portfolio import generate_portfolio
from app.models.generation import Generation
from app.models.user import User

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class PortfolioRequest(BaseModel):
    public_only: bool = False


@router.post("/generate")
async def generate(
    body: PortfolioRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    persona = await get_or_create_persona(session, user.id)
    result = await generate_portfolio(session, persona, public_only=body.public_only)
    gen = Generation(
        persona_id=persona.id,
        type="portfolio",
        title=persona.full_name,
        input=body.model_dump(),
        output={"portfolio": result["portfolio"]},  # HTML is large; regenerate on demand
    )
    session.add(gen)
    await session.flush()
    return {"id": str(gen.id), **result}
