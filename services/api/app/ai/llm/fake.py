"""Deterministic fake LLM provider for tests and offline development.

For extraction purposes it performs lightweight, input-driven heuristics so the
whole ingestion pipeline (chunk -> extract -> merge -> evidence) is genuinely
exercised without any network calls. The real provider does the smart version.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.ai.llm.base import LLMProvider, LLMResult, Message

_SKILL_VOCAB = [
    "python", "javascript", "typescript", "react", "next.js", "fastapi", "django",
    "flask", "postgresql", "mysql", "redis", "docker", "kubernetes", "aws", "gcp",
    "azure", "langchain", "rag", "pytorch", "tensorflow", "node.js", "go", "rust",
    "java", "c++", "sql", "git", "faiss", "pgvector", "llm", "nlp", "machine learning",
]
_ROLE_KEYWORDS = ("engineer", "developer", "scientist", "manager", "analyst", "designer",
                  "architect", "intern", "consultant", "researcher", "founder")
_EDU_KEYWORDS = ("bachelor", "master", "b.s.", "m.s.", "bsc", "msc", "b.tech", "m.tech", "phd")


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _line_with(text: str, needle: str) -> str:
    for ln in _lines(text):
        if needle.lower() in ln.lower():
            return ln
    return needle


def _extract_resume(text: str) -> dict[str, Any]:
    lines = _lines(text)
    lower = text.lower()

    skills = []
    seen = set()
    for kw in _SKILL_VOCAB:
        if kw not in seen and re.search(rf"(?<![\w.]){re.escape(kw)}(?![\w.])", lower):
            seen.add(kw)
            skills.append({"name": kw, "category": None, "quote": _line_with(text, kw)})

    full_name = None
    for ln in lines[:6]:
        if re.fullmatch(r"[A-Z][a-z]+(?: [A-Z][a-z]+){1,2}", ln):
            full_name = ln
            break

    headline = None
    for ln in lines[:6]:
        if any(k in ln.lower() for k in _ROLE_KEYWORDS) and len(ln) < 60:
            headline = ln
            break

    experiences = []
    for ln in lines:
        m = re.search(r"(?P<role>[A-Z][A-Za-z/ ]+?) at (?P<company>[A-Z][A-Za-z0-9&.,' ]+)", ln)
        if m and any(k in m.group("role").lower() for k in _ROLE_KEYWORDS):
            experiences.append({
                "role": m.group("role").strip(),
                "company": m.group("company").strip(),
                "start_date": None, "end_date": None,
                "description": None, "quote": ln,
            })

    projects = []
    for ln in lines:
        m = re.match(r"(?:Built|Created|Developed|Designed) (?P<name>.+)", ln, re.IGNORECASE)
        if m:
            techs = [kw for kw in _SKILL_VOCAB if kw in ln.lower()]
            name = re.split(r"\b(?:using|with)\b", m.group("name"), maxsplit=1)[0].strip(" .")
            projects.append({"name": name, "description": ln,
                             "technologies": techs, "quote": ln})

    education = []
    for ln in lines:
        if any(k in ln.lower() for k in _EDU_KEYWORDS):
            education.append({
                "institution": ln, "degree": None, "field_of_study": None, "quote": ln,
            })

    return {
        "full_name": full_name, "headline": headline, "location": None, "summary": None,
        "skills": skills, "experiences": experiences, "projects": projects,
        "education": education, "achievements": [],
    }


def _analyze_jd(text: str) -> dict[str, Any]:
    lines = _lines(text)
    lower = text.lower()

    techs = []
    for kw in _SKILL_VOCAB:
        if re.search(rf"(?<![\w.]){re.escape(kw)}(?![\w.])", lower):
            techs.append(kw)

    # Required vs preferred by surrounding keywords.
    required, preferred = [], []
    for kw in techs:
        line = _line_with(text, kw).lower()
        if any(w in line for w in ("prefer", "nice to have", "plus", "bonus")):
            preferred.append(kw)
        else:
            required.append(kw)

    title = None
    for ln in lines[:4]:
        if any(k in ln.lower() for k in _ROLE_KEYWORDS) and len(ln) < 80:
            title = ln
            break

    responsibilities = [
        ln.lstrip("-*• ").strip()
        for ln in lines
        if len(ln.split()) >= 5 and not any(k in ln.lower() for k in _EDU_KEYWORDS)
    ][:10]

    yrs = re.search(r"(\d+)\+?\s*years?", lower)
    education = next((ln for ln in lines if any(k in ln.lower() for k in _EDU_KEYWORDS)), None)

    return {
        "title": title,
        "required_skills": required,
        "preferred_skills": preferred,
        "technologies": techs,
        "responsibilities": responsibilities,
        "experience_years": int(yrs.group(1)) if yrs else None,
        "education": education,
        "domain": None,
    }


class FakeLLMProvider(LLMProvider):
    name = "fake"

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
        user_text = "\n".join(m["content"] for m in messages if m["role"] == "user")

        if purpose.startswith("extract"):
            payload = json.dumps(_extract_resume(user_text))
        elif purpose.startswith("analyze_jd"):
            payload = json.dumps(_analyze_jd(user_text))
        elif json_mode:
            payload = "{}"
        else:
            # Deterministic, grounded-looking echo for chat/generation paths.
            payload = f"[fake-llm:{purpose}] {user_text[:200]}"

        return LLMResult(
            text=payload,
            model=model,
            tokens_in=len(user_text.split()),
            tokens_out=len(payload.split()),
            latency_ms=0.0,
            purpose=purpose,
        )
