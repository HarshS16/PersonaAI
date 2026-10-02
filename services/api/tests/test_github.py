from __future__ import annotations

import uuid

from httpx import AsyncClient


async def _connect(client: AsyncClient, username: str = "octocat") -> dict:
    resp = await client.post("/sources/github/connect", json={"username": username})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _sync(job_id: str) -> dict:
    from app.ingestion.github_sync import sync_github_job

    return await sync_github_job(uuid.UUID(job_id))


async def test_connect_requires_username_or_oauth(auth_client: AsyncClient) -> None:
    resp = await auth_client.post("/sources/github/connect", json={})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "github_not_connected"


async def test_status_before_connect(auth_client: AsyncClient) -> None:
    resp = await auth_client.get("/sources/github/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["oauth_connected"] is False
    assert body["source_id"] is None


async def test_github_sync_creates_projects_and_skills(auth_client: AsyncClient) -> None:
    body = await _connect(auth_client)
    assert body["source"]["type"] == "github"
    summary = await _sync(body["job"]["id"])
    # Two non-fork repos -> two projects; languages -> skills.
    assert summary["created"]["projects"] == 2
    assert summary["created"]["skills"] >= 3

    full = (await auth_client.get("/persona/full")).json()
    projects = {p["name"] for p in full["facts"]["projects"]}
    assert "rag-search" in projects
    skills = {s["canonical_name"] for s in full["facts"]["skills"]}
    assert {"python", "typescript", "shell"}.issubset(skills)

    # Evidence is attributed to GitHub.
    py = next(s for s in full["facts"]["skills"] if s["canonical_name"] == "python")
    ev = (await auth_client.get(f"/persona/skills/{py['id']}/evidence")).json()
    assert ev[0]["locator"]["source"] == "github"


async def test_github_source_shows_in_sources_and_status(auth_client: AsyncClient) -> None:
    body = await _connect(auth_client)
    await _sync(body["job"]["id"])

    sources = (await auth_client.get("/sources")).json()
    gh = next(s for s in sources if s["type"] == "github")
    assert gh["status"] == "synced"
    assert gh["stats"]["repos"] == 2

    status = (await auth_client.get("/sources/github/status")).json()
    assert status["source_id"] is not None


async def test_github_merges_with_resume_skills(auth_client: AsyncClient) -> None:
    # Add Python manually first, then GitHub sync should add evidence, not duplicate.
    await auth_client.post("/persona/skills", json={"name": "Python"})
    body = await _connect(auth_client)
    await _sync(body["job"]["id"])

    full = (await auth_client.get("/persona/full")).json()
    pys = [s for s in full["facts"]["skills"] if s["canonical_name"] == "python"]
    assert len(pys) == 1  # merged, not duplicated
    assert pys[0]["evidence_count"] >= 2


async def test_reconnect_reuses_single_source(auth_client: AsyncClient) -> None:
    b1 = await _connect(auth_client)
    await _sync(b1["job"]["id"])
    b2 = await _connect(auth_client)
    assert b2["source"]["id"] == b1["source"]["id"]
    sources = (await auth_client.get("/sources")).json()
    assert sum(1 for s in sources if s["type"] == "github") == 1
