"""LLM factory and structured-output helper."""

from __future__ import annotations

import json
from functools import lru_cache

from pydantic import BaseModel, ValidationError

from app.ai.llm.base import LLMProvider, LLMResult, Message
from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("llm")


@lru_cache
def get_llm() -> LLMProvider:
    provider = settings.llm_provider.lower()
    if provider == "fake":
        from app.ai.llm.fake import FakeLLMProvider

        return FakeLLMProvider()
    if provider == "groq":
        from app.ai.llm.openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(
            api_key=settings.groq_api_key, base_url=settings.groq_base_url, name="groq"
        )
    if provider == "openai":
        from app.ai.llm.openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
            name="openai",
        )
    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")


def _extract_json(text: str) -> str:
    """Pull the first JSON object out of a completion, tolerating stray prose."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


async def complete_structured[T: BaseModel](
    schema: type[T],
    messages: list[Message],
    *,
    model: str,
    max_tokens: int = 4096,
    purpose: str = "extract",
    retries: int = 1,
) -> tuple[T, LLMResult]:
    """Return a validated instance of `schema` plus the raw result.

    Uses JSON mode and parses/repairs the output, retrying once on failure.
    """
    llm = get_llm()
    attempt = 0
    last_error: Exception | None = None
    result: LLMResult | None = None
    convo = list(messages)

    while attempt <= retries:
        result = await llm.complete(
            convo, model=model, max_tokens=max_tokens, temperature=0.1,
            json_mode=True, purpose=purpose,
        )
        try:
            data = json.loads(_extract_json(result.text))
            return schema.model_validate(data), result
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            log.warning("structured_parse_failed", attempt=attempt, error=str(exc)[:200])
            convo = [
                *messages,
                {"role": "assistant", "content": result.text[:2000]},
                {
                    "role": "user",
                    "content": "That was not valid JSON for the schema. Reply with ONLY the "
                    "corrected JSON object, no prose.",
                },
            ]
            attempt += 1

    # Give up gracefully with an empty instance rather than crashing ingestion.
    log.error("structured_giving_up", error=str(last_error)[:200])
    assert result is not None
    return schema.model_validate({}), result


__all__ = ["get_llm", "complete_structured", "LLMProvider", "LLMResult", "Message"]
