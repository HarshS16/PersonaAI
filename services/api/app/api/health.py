"""Liveness and readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.core.db import get_session

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: the process is up."""
    return {"status": "ok", "version": __version__}


@router.get("/health/ready")
async def ready(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    """Readiness: dependencies (DB) are reachable."""
    checks: dict[str, object] = {}
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # pragma: no cover - exercised via integration
        checks["database"] = f"error: {exc}"
    healthy = all(v == "ok" for v in checks.values())
    return {"status": "ok" if healthy else "degraded", "checks": checks}
