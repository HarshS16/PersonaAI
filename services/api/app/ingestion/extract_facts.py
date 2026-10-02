"""Run structured fact extraction over document text."""

from __future__ import annotations

from app.ai.extraction import ResumeExtraction
from app.ai.llm import LLMResult, complete_structured
from app.ai.llm.base import Message
from app.core.config import settings

_SYSTEM = """You extract structured professional facts from a document.

Rules:
- Extract ONLY information explicitly present in the text. Never invent or infer
  details that are not written.
- For every item, include a short VERBATIM quote copied from the text that
  supports it. If you cannot quote the text for a fact, do not include the fact.
- Prefer precise, de-duplicated entries.

Return a JSON object with these keys:
- full_name (string or null)
- headline (string or null): the person's professional title
- location (string or null)
- summary (string or null)
- skills: list of {name, category (or null), quote}
- experiences: list of {role, company (or null), start_date, end_date, description, quote}
- projects: list of {name, description, technologies (list), quote}
- education: list of {institution, degree, field_of_study, quote}
- achievements: list of {title, quote}

Output ONLY the JSON object."""


async def extract_resume(text: str) -> tuple[ResumeExtraction, LLMResult]:
    messages: list[Message] = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": f"Document text:\n\n{text[:16000]}"},
    ]
    return await complete_structured(
        ResumeExtraction,
        messages,
        model=settings.llm_model_strong,
        max_tokens=6000,
        purpose="extract_resume",
    )
