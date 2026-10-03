"""Tests for research import (Semantic Scholar / arXiv / ORCID)."""

from __future__ import annotations

import uuid

from httpx import AsyncClient


async def _connect(client: AsyncClient) -> dict:
    resp = await client.post(
        "/sources/research/connect",
        json={"provider": "semantic_scholar", "query": "Geoffrey Hinton"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _sync(job_id: str) -> dict:
    from app.ingestion.research_sync import sync_research_job
    return await sync_research_job(uuid.UUID(job_id))


async def test_research_connect_bad_provider(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        "/sources/research/connect",
        json={"provider": "pubmed", "query": "test"},
    )
    assert resp.status_code == 400


async def test_research_import_creates_publications(auth_client: AsyncClient) -> None:
    body = await _connect(auth_client)
    await _sync(body["job"]["id"])

    full = (await auth_client.get("/persona/full")).json()
    pubs = full["facts"].get("publications", [])
    assert len(pubs) >= 1
    titles = {p["title"] for p in pubs}
    assert "Attention Is All You Need" in titles


async def test_research_source_listed(auth_client: AsyncClient) -> None:
    body = await _connect(auth_client)
    await _sync(body["job"]["id"])

    sources = (await auth_client.get("/sources")).json()
    research = next(s for s in sources if s["type"] == "research")
    assert research["status"] == "synced"
    assert research["stats"]["papers"] >= 1
