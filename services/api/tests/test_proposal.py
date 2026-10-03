"""Tests for freelancer proposal generator and meeting prep."""

from __future__ import annotations

from httpx import AsyncClient


async def _seed(client: AsyncClient) -> None:
    await client.post("/persona/skills", json={"name": "Python"})
    await client.post("/persona/skills", json={"name": "FastAPI"})
    await client.post(
        "/persona/experiences",
        json={"role": "Backend Engineer", "company": "Acme Corp",
              "description": "Built REST APIs and microservices"},
    )
    await client.post(
        "/persona/projects",
        json={"name": "DataPipeline", "description": "ETL pipeline for analytics",
              "technologies": ["Python", "PostgreSQL"]},
    )


async def test_proposal_generate(auth_client: AsyncClient) -> None:
    await _seed(auth_client)
    resp = await auth_client.post(
        "/content/proposal",
        json={
            "project_description": (
                "Looking for a Python developer to build a REST API "
                "with FastAPI and PostgreSQL for our analytics platform."
            ),
            "platform": "upwork",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "content" in body
    assert body["platform"] == "upwork"
    assert "id" in body  # persisted as a generation


async def test_meeting_prep(auth_client: AsyncClient) -> None:
    await _seed(auth_client)
    resp = await auth_client.post(
        "/content/meeting-prep",
        json={
            "context": "Meeting with CTO of TechStartup about a backend engineering role",
            "focus": "technical",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "content" in body
    assert "id" in body


async def test_interview_feedback(auth_client: AsyncClient) -> None:
    await _seed(auth_client)
    resp = await auth_client.post(
        "/interview/feedback",
        json={
            "question": "Tell me about a project you built with Python.",
            "answer": (
                "I built a data pipeline that processes analytics "
                "events using Python and PostgreSQL."
            ),
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "feedback" in body
    assert "id" in body
