"""Run the evaluation and print a report.

    uv run python -m eval            # uses the configured provider (fake by default)
    LLM_PROVIDER=groq uv run python -m eval

Builds a throwaway synthetic persona in the database, evaluates, prints the
report, and rolls everything back so the database is left untouched.
"""

from __future__ import annotations

import asyncio
import json

from app.core.db import SessionLocal
from eval.personas import build_synthetic_persona
from eval.runner import run_eval

# Thresholds a healthy system should meet.
THRESHOLDS = {
    "retrieval_recall_at_k": 0.8,  # >=
    "negative_accuracy": 1.0,  # >=
    "groundedness": 0.9,  # >=
    "supported_pass_rate": 0.75,  # >=
    "hallucination_rate": 0.1,  # <=
}


async def main() -> int:
    async with SessionLocal() as session:
        persona = await build_synthetic_persona(session)
        await session.flush()
        report = await run_eval(session, persona)
        await session.rollback()  # never persist the eval persona

    data = report.as_dict()
    print(json.dumps(data, indent=2))

    print("\nThresholds:")
    ok = True
    for key, bound in THRESHOLDS.items():
        value = data[key]
        passed = value <= bound if key == "hallucination_rate" else value >= bound
        ok = ok and passed
        op = "<=" if key == "hallucination_rate" else ">="
        print(f"  [{'PASS' if passed else 'FAIL'}] {key} = {value} ({op} {bound})")

    print(f"\n{'ALL THRESHOLDS PASSED' if ok else 'SOME THRESHOLDS FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
