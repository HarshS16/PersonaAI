from __future__ import annotations

import uuid

from httpx import AsyncClient

RESUME = """Harsh Srivastava
AI Engineer

Experience
Senior Software Engineer at WebBee Global
Built a RAG pipeline using LangChain and FAISS

Skills
Python, FastAPI, React, PostgreSQL, Docker, LangChain

Education
Bachelor of Technology, IIT Delhi
"""


async def _seed(client: AsyncClient) -> None:
    from app.ingestion.pipeline import ingest_job

    resp = await client.post(
        "/documents/upload", files={"file": ("resume.txt", RESUME.encode(), "text/plain")}
    )
    await ingest_job(uuid.UUID(resp.json()["job"]["id"]))


async def test_portfolio_generate(auth_client: AsyncClient) -> None:
    await _seed(auth_client)
    resp = await auth_client.post("/portfolio/generate", json={})
    assert resp.status_code == 200
    body = resp.json()
    p = body["portfolio"]
    assert len(p["skills"]) >= 4
    assert len(p["experience"]) >= 1
    # A self-contained HTML document is rendered.
    assert body["html"].startswith("<!doctype html>")
    assert "<section>" in body["html"]
    assert "python" in body["html"].lower()


async def test_portfolio_public_only_empty_by_default(auth_client: AsyncClient) -> None:
    await _seed(auth_client)
    resp = await auth_client.post("/portfolio/generate", json={"public_only": True})
    # Facts are private by default, so public-only portfolio has no skills.
    assert resp.json()["portfolio"]["skills"] == []
