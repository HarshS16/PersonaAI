from __future__ import annotations

import uuid

from httpx import AsyncClient


async def _connect(client: AsyncClient, provider: str = "medium", handle: str = "octo") -> dict:
    resp = await client.post(
        "/sources/blog/connect", json={"provider": provider, "handle": handle}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _sync(job_id: str) -> dict:
    from app.ingestion.blog_sync import sync_blog_job

    return await sync_blog_job(uuid.UUID(job_id))


async def test_blog_connect_bad_provider(auth_client: AsyncClient) -> None:
    resp = await auth_client.post("/sources/blog/connect", json={"provider": "x", "handle": "a"})
    assert resp.status_code == 400


async def test_blog_sync_indexes_articles_and_skills(auth_client: AsyncClient) -> None:
    body = await _connect(auth_client)
    await _sync(body["job"]["id"])

    # Articles are searchable.
    search = (await auth_client.get("/search", params={"q": "RAG pipeline"})).json()
    assert any("rag" in e["text"].lower() for e in search["excerpts"])

    # Skills written about were merged (low-weight blog evidence).
    full = (await auth_client.get("/persona/full")).json()
    skills = {s["canonical_name"] for s in full["facts"]["skills"]}
    assert "langchain" in skills or "fastapi" in skills


async def test_blog_sync_computes_writing_style(auth_client: AsyncClient) -> None:
    body = await _connect(auth_client)
    await _sync(body["job"]["id"])
    style = (await auth_client.get("/persona/writing-style")).json()
    assert "avg_sentence_length" in style
    assert style["avg_sentence_length"] > 0


async def test_blog_source_listed(auth_client: AsyncClient) -> None:
    body = await _connect(auth_client)
    await _sync(body["job"]["id"])
    sources = (await auth_client.get("/sources")).json()
    blog = next(s for s in sources if s["type"] == "blog")
    assert blog["status"] == "synced"
    assert blog["stats"]["articles"] >= 1
