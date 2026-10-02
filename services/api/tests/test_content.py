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
"""

JD = "AI Engineer. Required: Python, FastAPI, RAG. Build LLM pipelines."


async def _seed(client: AsyncClient) -> None:
    from app.ingestion.pipeline import ingest_job

    resp = await client.post(
        "/documents/upload", files={"file": ("resume.txt", RESUME.encode(), "text/plain")}
    )
    await ingest_job(uuid.UUID(resp.json()["job"]["id"]))


async def test_generate_linkedin_post(auth_client: AsyncClient) -> None:
    await _seed(auth_client)
    resp = await auth_client.post(
        "/content/generate",
        json={"content_type": "linkedin_post", "topic": "my RAG work", "tone": "professional"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["content"]
    assert body["content_type"] == "linkedin_post"
    assert "warnings" in body
    assert "id" in body


async def test_generate_persisted(auth_client: AsyncClient) -> None:
    await _seed(auth_client)
    await auth_client.post("/content/generate", json={"topic": "my skills"})
    gens = (await auth_client.get("/generations")).json()
    assert any(g["type"].startswith("content:") for g in gens)


async def test_cover_letter(auth_client: AsyncClient) -> None:
    await _seed(auth_client)
    resp = await auth_client.post(
        "/content/cover-letter", json={"job_description": JD, "company": "Acme"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["content"]
    assert "python" in [m.lower() for m in body["matched"]]


async def test_application_answer(auth_client: AsyncClient) -> None:
    await _seed(auth_client)
    resp = await auth_client.post(
        "/content/application-answer",
        json={"question": "Why are you a good fit for an AI engineering role?"},
    )
    assert resp.status_code == 200
    assert resp.json()["content"]


async def test_content_validation(auth_client: AsyncClient) -> None:
    await _seed(auth_client)
    resp = await auth_client.post("/content/generate", json={"topic": "RAG"})
    # Warnings is a list (may be empty); the field exists and is well-formed.
    assert isinstance(resp.json()["warnings"], list)
