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

# Tests run against a DEDICATED database so they never truncate the dev data.
# Override with TEST_DATABASE_URL if needed. This must be set before app imports.
_TEST_DB = "persona_test"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    f"postgresql+asyncpg://persona:persona@localhost:5432/{_TEST_DB}",
)


@pytest.fixture(scope="session", autouse=True)
def _prepare_test_database() -> None:
    """Create and migrate the dedicated test database once per session."""
    import psycopg
    from alembic import command
    from alembic.config import Config

    admin_url = "postgresql://persona:persona@localhost:5432/postgres"
    with psycopg.connect(admin_url, autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (_TEST_DB,)
        ).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{_TEST_DB}"')

    command.upgrade(Config("alembic.ini"), "head")

# Tables truncated between tests. CASCADE handles FK order.
_TABLES = [
    "one_time_tokens",
    "refresh_tokens",
    "oauth_accounts",
    "chat_messages",
    "chat_sessions",
    "job_leads",
    "job_search_tasks",
    "generations",
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
