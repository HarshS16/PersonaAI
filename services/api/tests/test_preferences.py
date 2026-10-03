"""Tests for the inferred preferences flow."""

from __future__ import annotations

from httpx import AsyncClient


async def _seed_persona(client: AsyncClient) -> None:
    """Add some skills and an experience so inference has material."""
    await client.post(
        "/persona/skills",
        json={"name": "Python", "level": "expert"},
    )
    await client.post(
        "/persona/skills",
        json={"name": "TypeScript", "level": "advanced"},
    )
    await client.post(
        "/persona/skills",
        json={"name": "PostgreSQL", "level": "advanced"},
    )
    await client.post(
        "/persona/experiences",
        json={
            "role": "Senior Backend Engineer",
            "company": "Acme Corp",
            "description": "Built distributed systems in a remote team.",
        },
    )


async def test_infer_creates_pending_preferences(auth_client: AsyncClient) -> None:
    await _seed_persona(auth_client)
    resp = await auth_client.post("/preferences/infer")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] > 0
    keys = {p["key"] for p in body["inferred"]}
    assert "preferred_technologies" in keys
    assert "seniority_level" in keys


async def test_pending_lists_inferred(auth_client: AsyncClient) -> None:
    await _seed_persona(auth_client)
    await auth_client.post("/preferences/infer")
    pending = (await auth_client.get("/preferences/pending")).json()
    assert len(pending) > 0
    assert all(p["source"] == "inferred_pending" for p in pending)


async def test_confirm_changes_source(auth_client: AsyncClient) -> None:
    await _seed_persona(auth_client)
    await auth_client.post("/preferences/infer")
    pending = (await auth_client.get("/preferences/pending")).json()
    pref_id = pending[0]["id"]
    resp = await auth_client.post(f"/preferences/{pref_id}/confirm")
    assert resp.status_code == 200
    assert resp.json()["source"] == "confirmed"

    # No longer in pending list
    remaining = (await auth_client.get("/preferences/pending")).json()
    assert pref_id not in {p["id"] for p in remaining}


async def test_dismiss_deletes_preference(auth_client: AsyncClient) -> None:
    await _seed_persona(auth_client)
    await auth_client.post("/preferences/infer")
    pending = (await auth_client.get("/preferences/pending")).json()
    pref_id = pending[0]["id"]
    resp = await auth_client.delete(f"/preferences/{pref_id}/dismiss")
    assert resp.status_code == 204

    remaining = (await auth_client.get("/preferences/pending")).json()
    assert pref_id not in {p["id"] for p in remaining}


async def test_infer_idempotent(auth_client: AsyncClient) -> None:
    """Running infer twice doesn't duplicate preferences."""
    await _seed_persona(auth_client)
    await auth_client.post("/preferences/infer")
    second = (await auth_client.post("/preferences/infer")).json()
    assert second["count"] == 0  # all keys already exist


async def test_work_mode_inferred_from_remote(auth_client: AsyncClient) -> None:
    await _seed_persona(auth_client)
    resp = await auth_client.post("/preferences/infer")
    inferred = {p["key"]: p["value"] for p in resp.json()["inferred"]}
    assert inferred.get("work_mode") == "remote"
