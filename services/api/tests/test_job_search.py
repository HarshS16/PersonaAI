"""Tests for agentic job search (Phase 4)."""

from __future__ import annotations

from httpx import AsyncClient


async def _seed(client: AsyncClient) -> None:
    await client.post("/persona/skills", json={"name": "Python"})
    await client.post("/persona/skills", json={"name": "FastAPI"})
    await client.post(
        "/persona/experiences",
        json={
            "role": "Backend Engineer",
            "company": "Acme Corp",
            "description": "Built REST APIs and microservices",
        },
    )


async def test_job_search_flow(auth_client: AsyncClient) -> None:
    """Full agent flow: search → evaluate → approve → apply."""
    await _seed(auth_client)

    # 1. Search
    resp = await auth_client.post(
        "/agent/jobs/search",
        json={
            "query": (
                "Senior Python backend engineer, remote, "
                "working on API platforms"
            ),
            "criteria": {"location": "remote", "experience_level": "senior"},
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "task" in body
    assert "leads" in body
    assert body["task"]["status"] == "evaluated"
    assert len(body["leads"]) >= 1

    task_id = body["task"]["id"]
    lead_id = body["leads"][0]["id"]

    # 2. List tasks
    resp = await auth_client.get("/agent/jobs/tasks")
    assert resp.status_code == 200
    assert any(t["id"] == task_id for t in resp.json())

    # 3. Get leads
    resp = await auth_client.get(f"/agent/jobs/tasks/{task_id}/leads")
    assert resp.status_code == 200
    leads = resp.json()
    assert len(leads) >= 1
    assert leads[0]["fit_score"] >= 0

    # 4. Approve
    resp = await auth_client.post(f"/agent/jobs/leads/{lead_id}/approve")
    assert resp.status_code == 200
    assert resp.json()["approval_status"] == "approved"

    # 5. Apply (generates application)
    resp = await auth_client.post(f"/agent/jobs/leads/{lead_id}/apply")
    assert resp.status_code == 200
    app = resp.json()
    assert "cover_letter" in app
    assert "id" in app


async def test_reject_lead(auth_client: AsyncClient) -> None:
    await _seed(auth_client)

    resp = await auth_client.post(
        "/agent/jobs/search",
        json={"query": "Junior frontend developer React"},
    )
    assert resp.status_code == 201
    lead_id = resp.json()["leads"][0]["id"]

    resp = await auth_client.post(f"/agent/jobs/leads/{lead_id}/reject")
    assert resp.status_code == 200
    assert resp.json()["approval_status"] == "rejected"


async def test_apply_without_approval(auth_client: AsyncClient) -> None:
    await _seed(auth_client)

    resp = await auth_client.post(
        "/agent/jobs/search",
        json={"query": "Data engineer Python SQL"},
    )
    lead_id = resp.json()["leads"][0]["id"]

    # Should fail — not approved
    resp = await auth_client.post(f"/agent/jobs/leads/{lead_id}/apply")
    assert resp.status_code == 400
