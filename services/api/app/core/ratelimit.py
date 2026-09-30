"""Rate limiting via slowapi, backed by Redis in production.

Falls back to in-memory storage when Redis is unavailable (dev/tests).
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.core.config import settings

_is_test = settings.environment.lower() == "test"


def client_key(request: Request) -> str:
    """Rate-limit key: the real client IP.

    Behind the Next dev proxy (and any production reverse proxy) the direct peer
    is the proxy, so without this every user would share one bucket. We take the
    left-most X-Forwarded-For entry.

    SECURITY: X-Forwarded-For is client-spoofable unless a trusted proxy strips
    and sets it. In production this must run behind a proxy that overwrites the
    header, and the trusted-proxy hop count should be enforced (tracked for M10).
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(
    key_func=client_key,
    # In-memory storage in tests (and when Redis is only for the broker); Redis
    # in real deployments so limits hold across worker processes.
    storage_uri="memory://" if _is_test else settings.redis_url,
    default_limits=[],
    headers_enabled=True,
    enabled=not _is_test,
)
