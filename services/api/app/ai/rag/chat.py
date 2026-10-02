"""Persona chat: retrieve, assemble a grounded prompt, and expose citations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm.base import Message
from app.ai.rag.retrieval import RetrievedContext, build_context_block, retrieve
from app.models.persona import Persona

_SYSTEM = """You are {name}'s professional AI persona. You answer questions about
their skills, experience, projects, and background.

Rules:
- Answer using ONLY the context provided below. It is drawn from the person's
  own connected sources (resume, GitHub, manual entries).
- Cite the source excerpts you use with bracketed numbers like [1], [2].
- If the context does not support an answer, say so plainly — do not invent
  experience, projects, or skills.
- Be concise and speak in the third person about the person, or first person if
  the person is asking about themselves.

Context:
{context}
"""


@dataclass
class Citation:
    index: int
    type: str
    title: str

    def to_dict(self) -> dict[str, Any]:
        return {"index": self.index, "type": self.type, "title": self.title}


@dataclass
class ChatPrep:
    messages: list[Message]
    citations: list[Citation]
    context: RetrievedContext


def _citations(ctx: RetrievedContext) -> list[Citation]:
    cites: list[Citation] = []
    for i, c in enumerate(ctx.chunks, 1):
        cites.append(
            Citation(index=i, type=c.source_type or "source", title=c.source_title or "source")
        )
    return cites


async def prepare_chat(
    session: AsyncSession,
    persona: Persona,
    query: str,
    *,
    history: list[Message] | None = None,
) -> ChatPrep:
    ctx = await retrieve(session, persona, query)
    context_block = build_context_block(ctx)
    system = _SYSTEM.format(name=persona.full_name or "the user", context=context_block)

    messages: list[Message] = [{"role": "system", "content": system}]
    if history:
        messages.extend(history[-6:])  # keep recent turns
    messages.append({"role": "user", "content": query})

    return ChatPrep(messages=messages, citations=_citations(ctx), context=ctx)
