from __future__ import annotations

import uuid

from httpx import AsyncClient

RESUME = """Harsh Srivastava
AI Engineer

Experience
Senior Software Engineer at WebBee Global

Skills
Python, FastAPI, PostgreSQL
"""


async def _seed(client: AsyncClient) -> None:
    from app.ingestion.pipeline import ingest_job

    resp = await client.post(
        "/documents/upload", files={"file": ("resume.txt", RESUME.encode(), "text/plain")}
    )
    await ingest_job(uuid.UUID(resp.json()["job"]["id"]))


async def test_export_json(auth_client: AsyncClient) -> None:
    await _seed(auth_client)
    resp = await auth_client.get("/account/export")
    assert resp.status_code == 200
    assert resp.headers["content-disposition"].endswith('"persona-export.json"')
    body = resp.json()
    assert body["account"]["email"] == "persona@example.com"
    assert len(body["facts"]["skills"]) >= 3


async def test_export_zip(auth_client: AsyncClient) -> None:
    import io
    import zipfile

    await _seed(auth_client)
    resp = await auth_client.get("/account/export.zip")
    assert resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    assert "persona.json" in names
    assert any(n.startswith("documents/") for n in names)


async def test_public_profile_hides_private_by_default(auth_client: AsyncClient) -> None:
    await _seed(auth_client)
    persona = (await auth_client.get("/persona")).json()
    persona_id = persona["id"]

    # No auth header for the public endpoint.
    pub = await auth_client.get(f"/public/personas/{persona_id}", headers={"Authorization": ""})
    assert pub.status_code == 200
    body = pub.json()
    # Everything is private by default -> no skills exposed.
    assert body["skills"] == []


async def test_public_profile_shows_public_facts(auth_client: AsyncClient) -> None:
    await _seed(auth_client)
    persona = (await auth_client.get("/persona")).json()
    persona_id = persona["id"]

    skills = (await auth_client.get("/persona/skills")).json()
    target = skills[0]
    # Mark one skill public.
    await auth_client.patch(f"/persona/skills/{target['id']}", json={"visibility": "public"})

    pub = (await auth_client.get(f"/public/personas/{persona_id}")).json()
    public_names = {s["name"] for s in pub["skills"]}
    assert target["name"] in public_names
    assert len(pub["skills"]) == 1


async def test_disconnect_source_recomputes_confidence(auth_client: AsyncClient) -> None:
    await _seed(auth_client)
    # Confirm a skill exists with source evidence.
    skills = (await auth_client.get("/persona/skills")).json()
    py = next(s for s in skills if s["canonical_name"] == "python")
    assert py["evidence_count"] >= 1

    sources = (await auth_client.get("/sources")).json()
    await auth_client.delete(f"/sources/{sources[0]['id']}")

    skills_after = (await auth_client.get("/persona/skills")).json()
    py_after = next(s for s in skills_after if s["canonical_name"] == "python")
    # Evidence removed with the source; fact kept but demoted to inferred.
    assert py_after["evidence_count"] == 0
    assert py_after["state"] == "inferred"


async def test_delete_account(auth_client: AsyncClient) -> None:
    await _seed(auth_client)
    # Wrong password rejected.
    bad = await auth_client.post("/account/delete", json={"password": "wrong"})
    assert bad.status_code == 401

    resp = await auth_client.post("/account/delete", json={"password": "personapass1"})
    assert resp.status_code == 204

    # The user is gone; /persona now fails to authenticate the deleted user.
    me = await auth_client.get("/auth/me")
    assert me.status_code == 401
