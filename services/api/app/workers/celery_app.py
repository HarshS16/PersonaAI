"""Celery application.

On Windows, run the worker with the solo pool:
    uv run celery -A app.workers.celery_app worker --pool=solo -l info
"""

from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "personaai",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    task_default_retry_delay=5,
    task_time_limit=600,
    task_soft_time_limit=540,
    worker_max_tasks_per_child=100,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
)
