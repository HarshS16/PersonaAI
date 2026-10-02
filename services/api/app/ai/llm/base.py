"""LLM provider interface and shared result types.

Providers are intentionally thin: they turn messages into text or JSON and
report token/latency usage. Domain logic (prompts, retrieval, validation) lives
outside, so we are not coupled to any one provider or framework (SRD §39).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict


class Message(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass
class LLMResult:
    text: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0
    purpose: str = "general"
    raw: dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    """Chat-completion provider."""

    name: str = "base"

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        json_mode: bool = False,
        purpose: str = "general",
    ) -> LLMResult: ...

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.4,
        purpose: str = "chat",
    ) -> AsyncIterator[str]:
        """Default streaming: yield the whole completion at once.

        Providers that support token streaming override this.
        """
        result = await self.complete(
            messages, model=model, max_tokens=max_tokens, temperature=temperature, purpose=purpose
        )
        yield result.text
