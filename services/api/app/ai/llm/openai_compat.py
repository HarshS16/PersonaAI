"""OpenAI-compatible chat provider. Works with OpenAI and Groq (same wire
format, different base URL). GPT-OSS models on Groq spend reasoning tokens
before emitting output, so callers should budget max_tokens generously.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any, cast

from openai import AsyncOpenAI

from app.ai.llm.base import LLMProvider, LLMResult, Message


class OpenAICompatProvider(LLMProvider):
    def __init__(self, *, api_key: str, base_url: str | None = None, name: str = "openai") -> None:
        self.name = name
        self._api_key = api_key
        self._base_url = base_url or None

    def _new_client(self) -> AsyncOpenAI:
        # Create per call: the httpx client binds to the current event loop, so
        # a client cannot be shared across the worker's per-task loops.
        return AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        json_mode: bool = False,
        purpose: str = "general",
    ) -> LLMResult:
        start = time.perf_counter()
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        async with self._new_client() as client:
            resp = await client.chat.completions.create(**kwargs)
        latency_ms = (time.perf_counter() - start) * 1000

        choice = resp.choices[0]
        text = choice.message.content or ""
        usage = resp.usage
        return LLMResult(
            text=text,
            model=model,
            tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
            tokens_out=getattr(usage, "completion_tokens", 0) or 0,
            latency_ms=round(latency_ms, 2),
            purpose=purpose,
        )

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.4,
        purpose: str = "chat",
    ) -> AsyncIterator[str]:
        async with self._new_client() as client:
            stream = await client.chat.completions.create(
                model=model,
                messages=cast(Any, messages),
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            )
            async for chunk in cast(Any, stream):
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    yield delta
