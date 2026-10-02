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
    job_id = resp.json()["job"]["id"]
    await ingest_job(uuid.UUID(job_id))


async def test_search_returns_facts_and_excerpts(auth_client: AsyncClient) -> None:
    await _seed(auth_client)
    resp = await auth_client.get("/search", params={"q": "RAG"})
    assert resp.status_code == 200
    body = resp.json()
    # Structured project fact about RAG, and a keyword chunk hit.
    labels = " ".join(f["label"].lower() for f in body["facts"])
    assert "rag" in labels or any("rag" in e["text"].lower() for e in body["excerpts"])


async def test_search_structured_skill(auth_client: AsyncClient) -> None:
    await _seed(auth_client)
    resp = await auth_client.get("/search", params={"q": "python"})
    body = resp.json()
    skill_labels = {f["label"].lower() for f in body["facts"] if f["type"] == "skill"}
    assert "python" in skill_labels


async def test_chat_streams_answer_with_citations(auth_client: AsyncClient) -> None:
    await _seed(auth_client)
    async with auth_client.stream(
        "POST", "/chat", json={"message": "What projects involve RAG?"}
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        events = []
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                events.append(line[6:])
        types = [__import__("json").loads(e)["type"] for e in events]

    assert "session" in types
    assert "citations" in types
    assert "token" in types
    assert types[-1] == "done"


async def test_chat_persists_session_and_messages(auth_client: AsyncClient) -> None:
    await _seed(auth_client)
    session_id = None
    async with auth_client.stream(
        "POST", "/chat", json={"message": "What are my skills?"}
    ) as resp:
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                evt = __import__("json").loads(line[6:])
                if evt["type"] == "session":
                    session_id = evt["session_id"]

    assert session_id
    sessions = (await auth_client.get("/chat/sessions")).json()
    assert any(s["id"] == session_id for s in sessions)

    detail = (await auth_client.get(f"/chat/sessions/{session_id}")).json()
    roles = [m["role"] for m in detail["messages"]]
    assert roles[0] == "user"
    assert "assistant" in roles


async def test_chat_empty_persona_still_answers(auth_client: AsyncClient) -> None:
    # No sources connected — chat should still respond (grounded in nothing).
    async with auth_client.stream("POST", "/chat", json={"message": "Who am I?"}) as resp:
        assert resp.status_code == 200
        got_done = False
        async for line in resp.aiter_lines():
            if line.startswith("data: ") and '"type": "done"' in line:
                got_done = True
        assert got_done
