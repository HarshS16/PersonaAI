"""Ask-My-Persona chat (SSE streaming with citations) and personal search."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any, cast

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import get_llm
from app.ai.llm.base import Message
from app.ai.rag.chat import prepare_chat
from app.ai.rag.retrieval import retrieve
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import SessionLocal, get_session
from app.core.errors import NotFoundError
from app.domain.persona import get_or_create_persona
from app.models.chat import ChatMessage, ChatSession
from app.models.persona import Persona
from app.models.user import User

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: uuid.UUID | None = None


class ChatSessionOut(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: str


async def _get_or_create_session(
    session: AsyncSession, persona: Persona, session_id: uuid.UUID | None, first_message: str
) -> ChatSession:
    if session_id is not None:
        cs = await session.get(ChatSession, session_id)
        if cs is None or cs.persona_id != persona.id:
            raise NotFoundError("Chat session not found")
        return cs
    cs = ChatSession(persona_id=persona.id, title=first_message[:80])
    session.add(cs)
    await session.flush()
    return cs


async def _next_ordinal(session: AsyncSession, session_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.coalesce(func.max(ChatMessage.ordinal), -1)).where(
            ChatMessage.session_id == session_id
        )
    )
    return int(result.scalar_one()) + 1


async def _history(session: AsyncSession, session_id: uuid.UUID) -> list[Message]:
    rows = (
        await session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.ordinal)
        )
    ).scalars().all()
    return [cast(Message, {"role": r.role, "content": r.content}) for r in rows]


@router.post("/chat")
async def chat(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    persona = await get_or_create_persona(session, user.id)
    cs = await _get_or_create_session(session, persona, body.session_id, body.message)
    history = await _history(session, cs.id)

    ordinal = await _next_ordinal(session, cs.id)
    session.add(
        ChatMessage(session_id=cs.id, ordinal=ordinal, role="user", content=body.message)
    )

    prep = await prepare_chat(session, persona, body.message, history=history)
    citations = [c.to_dict() for c in prep.citations]
    session_id = cs.id
    assistant_ordinal = ordinal + 1
    messages = prep.messages

    await session.commit()  # persist user message before streaming

    async def event_stream() -> AsyncGenerator[str, None]:
        yield f"data: {json.dumps({'type': 'session', 'session_id': str(session_id)})}\n\n"
        yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"

        llm = get_llm()
        parts: list[str] = []
        try:
            async for token in llm.stream(
                messages, model=settings.llm_model_strong, max_tokens=1200, purpose="chat"
            ):
                parts.append(token)
                yield f"data: {json.dumps({'type': 'token', 'text': token})}\n\n"
        except Exception as exc:  # noqa: BLE001
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)[:200]})}\n\n"

        answer = "".join(parts)
        # Persist the assistant message in a fresh session (request one is closed).
        async with SessionLocal() as s:
            s.add(
                ChatMessage(
                    session_id=session_id,
                    ordinal=assistant_ordinal,
                    role="assistant",
                    content=answer,
                    citations=citations,
                )
            )
            await s.commit()

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/chat/sessions")
async def list_sessions(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    persona = await get_or_create_persona(session, user.id)
    rows = (
        await session.execute(
            select(ChatSession)
            .where(ChatSession.persona_id == persona.id)
            .order_by(ChatSession.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    return [
        {"id": str(r.id), "title": r.title, "created_at": r.created_at.isoformat()} for r in rows
    ]


@router.get("/chat/sessions/{session_id}")
async def get_session_messages(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    persona = await get_or_create_persona(session, user.id)
    cs = await session.get(ChatSession, session_id)
    if cs is None or cs.persona_id != persona.id:
        raise NotFoundError("Chat session not found")
    rows = (
        await session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.ordinal)
        )
    ).scalars().all()
    return {
        "id": str(cs.id),
        "title": cs.title,
        "messages": [
            {"role": r.role, "content": r.content, "citations": r.citations} for r in rows
        ],
    }


@router.get("/search")
async def search(
    q: str = Query(min_length=1, max_length=400),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    persona = await get_or_create_persona(session, user.id)
    ctx = await retrieve(session, persona, q)
    return {
        "facts": [
            {
                "type": f.entity_type,
                "id": str(f.entity_id),
                "label": f.label,
                "detail": f.detail,
                "confidence": f.confidence,
            }
            for f in ctx.facts
        ],
        "excerpts": [
            {
                "chunk_id": str(c.chunk_id),
                "text": c.text[:400],
                "source_title": c.source_title,
                "source_type": c.source_type,
                "score": c.score,
            }
            for c in ctx.chunks
        ],
    }
