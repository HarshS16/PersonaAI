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


async def test_dashboard_empty(auth_client: AsyncClient) -> None:
    resp = await auth_client.get("/dashboard")
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_sources"] is False
    assert body["counts"]["skills"] == 0


async def test_dashboard_populated(auth_client: AsyncClient) -> None:
    await _seed(auth_client)
    body = (await auth_client.get("/dashboard")).json()
    assert body["has_sources"] is True
    assert body["counts"]["skills"] >= 4
    assert len(body["top_skills"]) >= 1
    assert len(body["timeline"]) >= 1
    assert any(a["kind"] == "source_synced" for a in body["recent_activity"])


async def test_persona_graph(auth_client: AsyncClient) -> None:
    await _seed(auth_client)
    body = (await auth_client.get("/persona/graph")).json()
    node_types = {n["type"] for n in body["nodes"]}
    assert "persona" in node_types
    assert "skill" in node_types
    # Every non-persona node is connected back to the persona or a project.
    assert len(body["edges"]) >= len(body["nodes"]) - 1
    assert body["evidence_total"] >= 1


async def test_graph_not_shadowed_by_resource_route(auth_client: AsyncClient) -> None:
    # /persona/graph must resolve to the graph, not the fact-resource 404.
    resp = await auth_client.get("/persona/graph")
    assert resp.status_code == 200
    assert "nodes" in resp.json()
