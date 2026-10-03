"""Celery tasks."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from app.workers.celery_app import celery_app


@celery_app.task(name="ping", bind=True, max_retries=3)  # type: ignore[untyped-decorator]
def ping(self: object, value: str = "pong") -> str:
    """Trivial task used to verify the broker/worker wiring."""
    return value


@celery_app.task(  # type: ignore[untyped-decorator]
    name="ingest_document",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    acks_late=True,
)
def ingest_document_task(self: Any, job_id: str) -> dict[str, Any]:
    """Run a document-ingestion job, retrying with backoff on failure.

    Each task runs on its own asyncio loop (solo pool), so it builds a fresh
    engine + session factory bound to that loop and disposes it at the end —
    the module-level engine cannot be reused across per-task loops.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings
    from app.ingestion.pipeline import ingest_job

    async def _main() -> dict[str, Any]:
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        try:
            return await ingest_job(uuid.UUID(job_id), session_factory=factory)
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_main())
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc) from exc


@celery_app.task(  # type: ignore[untyped-decorator]
    name="sync_github",
    bind=True,
    max_retries=3,
    default_retry_delay=15,
    acks_late=True,
)
def sync_github_task(self: Any, job_id: str) -> dict[str, Any]:
    """Sync a GitHub source, retrying with backoff on failure."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings
    from app.ingestion.github_sync import sync_github_job

    async def _main() -> dict[str, Any]:
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        try:
            return await sync_github_job(uuid.UUID(job_id), session_factory=factory)
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_main())
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc) from exc


@celery_app.task(  # type: ignore[untyped-decorator]
    name="sync_blog",
    bind=True,
    max_retries=3,
    default_retry_delay=15,
    acks_late=True,
)
def sync_blog_task(self: Any, job_id: str) -> dict[str, Any]:
    """Sync a blog/RSS source, retrying with backoff on failure."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings
    from app.ingestion.blog_sync import sync_blog_job

    async def _main() -> dict[str, Any]:
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        try:
            return await sync_blog_job(uuid.UUID(job_id), session_factory=factory)
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_main())
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc) from exc


@celery_app.task(  # type: ignore[untyped-decorator]
    name="sync_linkedin",
    bind=True,
    max_retries=3,
    default_retry_delay=15,
    acks_late=True,
)
def sync_linkedin_task(self: Any, job_id: str) -> dict[str, Any]:
    """Sync a LinkedIn data-export source."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings
    from app.ingestion.linkedin_sync import sync_linkedin_job

    async def _main() -> dict[str, Any]:
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        try:
            return await sync_linkedin_job(uuid.UUID(job_id), session_factory=factory)
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_main())
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc) from exc


@celery_app.task(  # type: ignore[untyped-decorator]
    name="sync_x",
    bind=True,
    max_retries=3,
    default_retry_delay=15,
    acks_late=True,
)
def sync_x_task(self: Any, job_id: str) -> dict[str, Any]:
    """Sync an X/Twitter archive source."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings
    from app.ingestion.x_sync import sync_x_job

    async def _main() -> dict[str, Any]:
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        try:
            return await sync_x_job(uuid.UUID(job_id), session_factory=factory)
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_main())
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc) from exc


@celery_app.task(  # type: ignore[untyped-decorator]
    name="sync_research",
    bind=True,
    max_retries=3,
    default_retry_delay=15,
    acks_late=True,
)
def sync_research_task(self: Any, job_id: str) -> dict[str, Any]:
    """Sync a research source (Semantic Scholar / arXiv / ORCID)."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings
    from app.ingestion.research_sync import sync_research_job

    async def _main() -> dict[str, Any]:
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        try:
            return await sync_research_job(uuid.UUID(job_id), session_factory=factory)
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_main())
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc) from exc
