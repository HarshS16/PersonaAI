"""Shared pytest fixtures.

The app is exercised via httpx's ASGI transport (no running server needed).
Integration tests that touch the DB expect the docker-compose Postgres to be up;
each test starts from clean auth tables.
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

# Tables truncated between tests. CASCADE handles FK order.
_TABLES = [
    "one_time_tokens",
    "refresh_tokens",
    "oauth_accounts",
    "chat_messages",
    "chat_sessions",
    "ai_calls",
    "chunks",
    "documents",
    "jobs",
    "conflicts",
    "sources",
    "evidence",
    "persona_versions",
    "skills",
    "experiences",
    "projects",
    "education",
    "achievements",
    "publications",
    "certifications",
    "preferences",
    "knowledge_areas",
    "writing_styles",
    "personas",
    "users",
]


@pytest.fixture(autouse=True)
async def _clean_db() -> AsyncGenerator[None, None]:
    from sqlalchemy import text

    from app.core.db import SessionLocal

    async with SessionLocal() as session:
        await session.execute(text(f"TRUNCATE {', '.join(_TABLES)} RESTART IDENTITY CASCADE"))
        await session.commit()
    yield


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    from app.main import create_app

    app = create_app()
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.fixture
async def auth_client(client: AsyncClient) -> AsyncClient:
    """A client signed up and carrying a Bearer access token."""
    resp = await client.post(
        "/auth/signup",
        json={"email": "persona@example.com", "password": "personapass1", "name": "Persona"},
    )
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
