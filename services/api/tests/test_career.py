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

JD = """Senior AI Engineer

We are looking for an engineer with 3 years of experience.
Required: Python, FastAPI, PostgreSQL, RAG systems.
Preferred: Kubernetes, AWS.
Responsibilities include building scalable backend services and LLM pipelines.
Bachelor of Technology in Computer Science.
"""


async def _seed(client: AsyncClient) -> None:
    from app.ingestion.pipeline import ingest_job

    resp = await client.post(
        "/documents/upload", files={"file": ("resume.txt", RESUME.encode(), "text/plain")}
    )
    await ingest_job(uuid.UUID(resp.json()["job"]["id"]))


async def test_jd_analyze_and_gap(auth_client: AsyncClient) -> None:
    await _seed(auth_client)
    resp = await auth_client.post("/jd/analyze", json={"job_description": JD})
    assert resp.status_code == 200
    body = resp.json()
    techs = set(body["analysis"]["technologies"])
    assert "python" in techs and "fastapi" in techs

    gap = body["gap"]
    # Python/FastAPI are in the persona -> strong; Kubernetes is not -> none.
    assert "python" in gap["strongly_supported"]
    assert "kubernetes" in gap["not_demonstrated"]


async def test_resume_generation(auth_client: AsyncClient) -> None:
    await _seed(auth_client)
    resp = await auth_client.post(
        "/resume/generate", json={"job_description": JD, "target_role": "AI Engineer"}
    )
    assert resp.status_code == 200
    body = resp.json()
    resume = body["resume"]
    assert resume["headline"] == "AI Engineer"
    assert "python" in [s.lower() for s in resume["skills"]]
    assert len(resume["experience"]) >= 1
    # ATS coverage is computed; Kubernetes/AWS are missing.
    assert 0.0 <= body["ats"]["keyword_coverage"] <= 1.0
    assert "kubernetes" in body["missing_requirements"]
    assert body["markdown"].startswith("#")


async def test_resume_validator_drops_unsupported_bullet(auth_client: AsyncClient) -> None:
    # Manually add an experience whose highlight overclaims a figure not in evidence.
    created = await auth_client.post(
        "/persona/experiences",
        json={
            "role": "Engineer",
            "company": "Acme",
            "description": "Worked on backend services",
            "highlights": ["Led a team of 500 engineers across 9 countries"],
        },
    )
    assert created.status_code == 201
    resp = await auth_client.post("/resume/generate", json={"job_description": JD})
    body = resp.json()
    acme = next((e for e in body["resume"]["experience"] if e["company"] == "Acme"), None)
    assert acme is not None
    # The fabricated figures are unsupported -> that bullet is dropped.
    texts = " ".join(b["text"] for b in acme["bullets"])
    assert "500" not in texts


async def test_interview_modes(auth_client: AsyncClient) -> None:
    await _seed(auth_client)
    tech = await auth_client.post("/interview/start", json={"mode": "technical"})
    assert tech.status_code == 200
    assert len(tech.json()["questions"]) >= 1

    bad = await auth_client.post("/interview/start", json={"mode": "nonsense"})
    assert bad.status_code == 400

    # With a JD, weak-area questions are appended.
    withjd = await auth_client.post(
        "/interview/start", json={"mode": "behavioral", "job_description": JD}
    )
    focuses = " ".join(q["focus"] for q in withjd.json()["questions"])
    assert "gap:" in focuses


async def test_generations_persisted(auth_client: AsyncClient) -> None:
    await _seed(auth_client)
    await auth_client.post("/jd/analyze", json={"job_description": JD})
    gens = (await auth_client.get("/generations", params={"type": "jd_analysis"})).json()
    assert len(gens) >= 1
    detail = (await auth_client.get(f"/generations/{gens[0]['id']}")).json()
    assert detail["type"] == "jd_analysis"
    assert "analysis" in detail["output"]
