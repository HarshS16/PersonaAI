from __future__ import annotations

import uuid

from httpx import AsyncClient

RESUME = """Harsh Srivastava
AI Engineer
Bangalore, India

Experience
Senior Software Engineer at WebBee Global
Built a RAG pipeline using LangChain and FAISS

Skills
Python, FastAPI, React, PostgreSQL, Docker, LangChain

Education
Bachelor of Technology in Computer Science, IIT
"""


async def _upload(client: AsyncClient, text: str = RESUME, name: str = "resume.txt") -> dict:
    resp = await client.post(
        "/documents/upload",
        files={"file": (name, text.encode(), "text/plain")},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _ingest(job_id: str) -> dict:
    from app.ingestion.pipeline import ingest_job

    return await ingest_job(uuid.UUID(job_id))


async def test_upload_creates_source_and_job(auth_client: AsyncClient) -> None:
    body = await _upload(auth_client)
    assert body["source"]["type"] == "resume"
    assert body["job"]["status"] == "queued"
    assert body["duplicate"] is False


async def test_duplicate_upload_detected(auth_client: AsyncClient) -> None:
    await _upload(auth_client)
    body = await _upload(auth_client)
    assert body["duplicate"] is True


async def test_unsupported_file_rejected(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        "/documents/upload", files={"file": ("x.exe", b"MZ", "application/octet-stream")}
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "unsupported_file"


async def test_full_ingestion_populates_persona_with_evidence(auth_client: AsyncClient) -> None:
    body = await _upload(auth_client)
    summary = await _ingest(body["job"]["id"])
    assert summary["created"]["skills"] >= 4

    full = (await auth_client.get("/persona/full")).json()
    skills = full["facts"]["skills"]
    names = {s["canonical_name"] for s in skills}
    assert {"python", "fastapi", "react", "postgresql"}.issubset(names)
    # Ingested facts are 'verified' and evidence-backed.
    py = next(s for s in skills if s["canonical_name"] == "python")
    assert py["state"] == "verified"

    ev = (await auth_client.get(f"/persona/skills/{py['id']}/evidence")).json()
    assert len(ev) >= 1
    assert ev[0]["content"]  # a verbatim quote
    assert ev[0]["source_id"] is not None

    # Experience, project, education were extracted too.
    assert len(full["facts"]["experiences"]) >= 1
    assert len(full["facts"]["projects"]) >= 1
    assert len(full["facts"]["education"]) >= 1


async def test_job_progress_reaches_done(auth_client: AsyncClient) -> None:
    body = await _upload(auth_client)
    await _ingest(body["job"]["id"])
    job = (await auth_client.get(f"/jobs/{body['job']['id']}")).json()
    assert job["status"] == "succeeded"
    assert job["progress"] == 1.0


async def test_identity_merges_when_empty(auth_client: AsyncClient) -> None:
    body = await _upload(auth_client)
    await _ingest(body["job"]["id"])
    persona = (await auth_client.get("/persona")).json()
    assert persona["headline"] == "AI Engineer"
    assert persona["full_name"] == "Harsh Srivastava"


async def test_conflicting_title_raises_conflict(auth_client: AsyncClient) -> None:
    # Pre-set a different headline, then ingest one that disagrees.
    await auth_client.patch("/persona", json={"headline": "Software Engineer"})
    body = await _upload(auth_client)
    summary = await _ingest(body["job"]["id"])
    assert summary["conflicts"] >= 1

    conflicts = (await auth_client.get("/conflicts")).json()
    assert len(conflicts) >= 1
    headline_conflict = next(c for c in conflicts if c["field"] == "headline")
    values = {cand["value"] for cand in headline_conflict["candidates"]}
    assert "Software Engineer" in values and "AI Engineer" in values

    # Persona headline was NOT silently overwritten.
    persona = (await auth_client.get("/persona")).json()
    assert persona["headline"] == "Software Engineer"

    # Resolve in favor of the new value.
    resolved = await auth_client.post(
        f"/conflicts/{headline_conflict['id']}/resolve", json={"chosen_value": "AI Engineer"}
    )
    assert resolved.status_code == 200
    persona = (await auth_client.get("/persona")).json()
    assert persona["headline"] == "AI Engineer"


async def test_second_source_raises_evidence_count(auth_client: AsyncClient) -> None:
    b1 = await _upload(auth_client)
    await _ingest(b1["job"]["id"])
    # A different document (different bytes) with overlapping skills.
    b2 = await _upload(auth_client, text=RESUME + "\nAdditional: Python expert.\n", name="r2.txt")
    await _ingest(b2["job"]["id"])

    full = (await auth_client.get("/persona/full")).json()
    py = next(s for s in full["facts"]["skills"] if s["canonical_name"] == "python")
    assert py["evidence_count"] >= 2
