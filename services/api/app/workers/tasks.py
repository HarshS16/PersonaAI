"""Celery tasks. Real ingestion tasks are added in M3; this is the sample/ping."""

from __future__ import annotations

from app.workers.celery_app import celery_app


@celery_app.task(name="ping", bind=True, max_retries=3)  # type: ignore[untyped-decorator]
def ping(self: object, value: str = "pong") -> str:
    """Trivial task used to verify the broker/worker wiring."""
    return value
