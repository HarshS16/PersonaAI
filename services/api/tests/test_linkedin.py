"""Tests for LinkedIn data-export import."""

from __future__ import annotations

import csv
import io
import uuid
import zipfile

from httpx import AsyncClient


def _make_linkedin_zip() -> bytes:
    """Build a minimal LinkedIn export ZIP with Profile, Skills, Positions, Education."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        # Profile.csv
        profile = io.StringIO()
        w = csv.DictWriter(profile, fieldnames=["First Name", "Last Name", "Headline", "Summary"])
        w.writeheader()
        w.writerow({
            "First Name": "Jane", "Last Name": "Doe",
            "Headline": "Senior Engineer", "Summary": "Builds distributed systems",
        })
        zf.writestr("Profile.csv", profile.getvalue())

        # Skills.csv
        skills = io.StringIO()
        w = csv.DictWriter(skills, fieldnames=["Name"])
        w.writeheader()
        for s in ["Python", "Kubernetes", "GraphQL"]:
            w.writerow({"Name": s})
        zf.writestr("Skills.csv", skills.getvalue())

        # Positions.csv
        pos = io.StringIO()
        fields = ["Title", "Company Name", "Started On", "Finished On", "Description"]
        w = csv.DictWriter(pos, fieldnames=fields)
        w.writeheader()
        w.writerow({
            "Title": "Staff Engineer", "Company Name": "Acme Corp",
            "Started On": "Jan 2020", "Finished On": "Dec 2023",
            "Description": "Led backend platform team",
        })
        zf.writestr("Positions.csv", pos.getvalue())

        # Education.csv
        edu = io.StringIO()
        w = csv.DictWriter(edu, fieldnames=["School Name", "Degree Name", "Field Of Study"])
        w.writeheader()
        w.writerow({"School Name": "MIT", "Degree Name": "BS", "Field Of Study": "CS"})
        zf.writestr("Education.csv", edu.getvalue())

    return buf.getvalue()


async def _upload(client: AsyncClient) -> dict:
    data = _make_linkedin_zip()
    resp = await client.post(
        "/sources/linkedin/upload",
        files={"file": ("linkedin_export.zip", data, "application/zip")},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _sync(job_id: str) -> dict:
    from app.ingestion.linkedin_sync import sync_linkedin_job
    return await sync_linkedin_job(uuid.UUID(job_id))


async def test_linkedin_upload_bad_extension(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        "/sources/linkedin/upload",
        files={"file": ("data.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 400


async def test_linkedin_import_merges_facts(auth_client: AsyncClient) -> None:
    body = await _upload(auth_client)
    assert body["duplicate"] is False
    await _sync(body["job"]["id"])

    full = (await auth_client.get("/persona/full")).json()
    skills = {s["canonical_name"] for s in full["facts"]["skills"]}
    assert "python" in skills
    assert "kubernetes" in skills

    exp_titles = {e["role"] for e in full["facts"]["experiences"]}
    assert "Staff Engineer" in exp_titles

    edu_schools = {e["institution"] for e in full["facts"]["education"]}
    assert "MIT" in edu_schools


async def test_linkedin_source_listed(auth_client: AsyncClient) -> None:
    body = await _upload(auth_client)
    await _sync(body["job"]["id"])

    sources = (await auth_client.get("/sources")).json()
    li = next(s for s in sources if s["type"] == "linkedin")
    assert li["status"] == "synced"
