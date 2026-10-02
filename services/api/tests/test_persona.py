from __future__ import annotations

from httpx import AsyncClient


async def test_get_persona_bootstraps(auth_client: AsyncClient) -> None:
    resp = await auth_client.get("/persona")
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] >= 1
    assert body["completeness"] == 0.0


async def test_update_identity(auth_client: AsyncClient) -> None:
    resp = await auth_client.patch(
        "/persona", json={"headline": "AI Engineer", "summary": "Builds RAG systems"}
    )
    assert resp.status_code == 200
    assert resp.json()["headline"] == "AI Engineer"


async def test_create_skill_has_evidence_and_canonical(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        "/persona/skills", json={"name": "ReactJS", "category": "Frontend"}
    )
    assert resp.status_code == 201
    skill = resp.json()
    assert skill["canonical_name"] == "react"
    assert skill["state"] == "user_confirmed"
    assert skill["confidence"] == 1.0

    ev = await auth_client.get(f"/persona/skills/{skill['id']}/evidence")
    assert ev.status_code == 200
    assert len(ev.json()) == 1
    assert ev.json()[0]["state"] == "user_confirmed"


async def test_fact_crud_cycle(auth_client: AsyncClient) -> None:
    created = await auth_client.post(
        "/persona/projects",
        json={"name": "RAG Pipeline", "technologies": ["LangChain", "FAISS"]},
    )
    pid = created.json()["id"]

    listed = await auth_client.get("/persona/projects")
    assert len(listed.json()) == 1

    patched = await auth_client.patch(f"/persona/projects/{pid}", json={"role": "Lead"})
    assert patched.json()["role"] == "Lead"

    deleted = await auth_client.delete(f"/persona/projects/{pid}")
    assert deleted.status_code == 204
    assert await (await auth_client.get("/persona/projects")).aread() is not None
    assert len((await auth_client.get("/persona/projects")).json()) == 0


async def test_unknown_resource_404(auth_client: AsyncClient) -> None:
    resp = await auth_client.get("/persona/nonsense")
    assert resp.status_code == 404


async def test_validation_error(auth_client: AsyncClient) -> None:
    resp = await auth_client.post("/persona/skills", json={"category": "no name"})
    assert resp.status_code == 422


async def test_confirm_inferred_fact(auth_client: AsyncClient) -> None:
    created = await auth_client.post("/persona/experiences", json={"role": "Engineer"})
    eid = created.json()["id"]
    resp = await auth_client.post(f"/persona/experiences/{eid}/confirm")
    assert resp.status_code == 200
    assert resp.json()["state"] == "user_confirmed"


async def test_completeness_increases(auth_client: AsyncClient) -> None:
    before = (await auth_client.get("/persona")).json()["completeness"]
    await auth_client.patch(
        "/persona", json={"headline": "X", "summary": "Y", "full_name": "Z"}
    )
    for i in range(5):
        await auth_client.post("/persona/skills", json={"name": f"Skill{i}"})
    await auth_client.post("/persona/experiences", json={"role": "Engineer"})
    after = (await auth_client.get("/persona")).json()["completeness"]
    assert after > before


async def test_full_payload(auth_client: AsyncClient) -> None:
    await auth_client.post("/persona/skills", json={"name": "Python"})
    resp = await auth_client.get("/persona/full")
    assert resp.status_code == 200
    body = resp.json()
    assert "persona" in body and "facts" in body
    assert len(body["facts"]["skills"]) == 1


async def test_version_snapshot_and_restore(auth_client: AsyncClient) -> None:
    # v1 -> add identity (snapshots v1) and a skill
    await auth_client.patch("/persona", json={"headline": "First"})
    await auth_client.post("/persona/skills", json={"name": "Python"})

    versions = await auth_client.get("/persona/meta/versions")
    assert versions.status_code == 200
    assert len(versions.json()) >= 1
    first_version_id = versions.json()[-1]["id"]  # oldest

    # Change identity again, then restore the first snapshot.
    await auth_client.patch("/persona", json={"headline": "Second"})
    restored = await auth_client.post(f"/persona/meta/versions/{first_version_id}/restore")
    assert restored.status_code == 200
    # The first snapshot had no headline (taken before the first patch applied).
    current = (await auth_client.get("/persona")).json()
    assert current["headline"] is None
