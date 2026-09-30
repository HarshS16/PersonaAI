"""Shared pytest fixtures.

The app is exercised via httpx's ASGI transport (no running server needed).
Integration tests that touch the DB expect the docker-compose Postgres to be up.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("LLM_PROVIDER", "fake")
os.environ.setdefault("EMBEDDING_PROVIDER", "fake")


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    from app.main import create_app

    app = create_app()
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
