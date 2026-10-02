from __future__ import annotations

from app.ai.rag.validation import (
    ClaimStatus,
    apply_verdicts,
    validate_claim,
    validate_text,
)

EVIDENCE = (
    "Worked on a RAG pipeline using LangChain and FAISS. "
    "Software Engineer at WebBee Global. Built backend services with FastAPI and PostgreSQL."
)


def test_supported_claim_allowed() -> None:
    v = validate_claim("Built a RAG pipeline with LangChain and FAISS", EVIDENCE)
    assert v.status == ClaimStatus.allow


def test_unsupported_number_rejected() -> None:
    v = validate_claim("Led a team of 20 engineers", EVIDENCE)
    # Both an unsupported number and a leadership claim; number check fires first.
    assert v.status == ClaimStatus.reject


def test_leadership_without_evidence_downgraded() -> None:
    v = validate_claim("Led the backend services effort", EVIDENCE)
    assert v.status == ClaimStatus.downgrade
    assert v.suggestion and "worked on" in v.suggestion.lower()


def test_unrelated_claim_rejected() -> None:
    v = validate_claim("Expert in Kubernetes and cloud infrastructure", EVIDENCE)
    assert v.status == ClaimStatus.reject


def test_apply_verdicts_drops_rejected() -> None:
    text = "Built a RAG pipeline with FastAPI. Led a team of 20 engineers."
    verdicts = validate_text(text, EVIDENCE)
    rebuilt = apply_verdicts(verdicts)
    assert "RAG" in rebuilt or "FastAPI" in rebuilt
    assert "20" not in rebuilt
