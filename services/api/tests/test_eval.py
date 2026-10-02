"""The evaluation harness must meet quality thresholds (SRD §62)."""

from __future__ import annotations

import pytest

from eval.personas import build_synthetic_persona
from eval.runner import run_eval


@pytest.fixture
async def eval_report():  # type: ignore[no-untyped-def]
    from app.core.db import SessionLocal

    async with SessionLocal() as session:
        persona = await build_synthetic_persona(session)
        await session.flush()
        report = await run_eval(session, persona)
        await session.rollback()
    return report


async def test_retrieval_recall(eval_report) -> None:  # type: ignore[no-untyped-def]
    assert eval_report.retrieval_recall_at_k >= 0.8


async def test_negative_accuracy(eval_report) -> None:  # type: ignore[no-untyped-def]
    # Absent skills (AWS, Kubernetes…) must never surface as structured facts.
    assert eval_report.negative_accuracy == 1.0


async def test_groundedness(eval_report) -> None:  # type: ignore[no-untyped-def]
    assert eval_report.groundedness >= 0.9


async def test_hallucination_rate_low(eval_report) -> None:  # type: ignore[no-untyped-def]
    # Fabricated claims (fake headcounts, AWS, huge budgets) must be blocked.
    assert eval_report.hallucination_rate <= 0.1


async def test_supported_claims_pass(eval_report) -> None:  # type: ignore[no-untyped-def]
    assert eval_report.supported_pass_rate >= 0.75
