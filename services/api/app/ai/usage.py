"""Persist AI-call accounting (tokens, latency) for observability (SRD §61)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm.base import LLMResult
from app.models.ingestion import AiCall


async def record_ai_call(
    session: AsyncSession, result: LLMResult, *, persona_id: uuid.UUID | None, provider: str
) -> None:
    session.add(
        AiCall(
            persona_id=persona_id,
            provider=provider,
            model=result.model,
            purpose=result.purpose,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            latency_ms=result.latency_ms,
        )
    )
