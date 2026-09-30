"""Rate limiting via slowapi, backed by Redis in production.

Falls back to in-memory storage when Redis is unavailable (dev/tests).
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.redis_url,
    default_limits=[],
    headers_enabled=True,
)
