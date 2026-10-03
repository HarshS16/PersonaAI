"""Tests for public persona, slug lookup, and public Ask AI."""

from __future__ import annotations

from httpx import AsyncClient


async def _seed(client: AsyncClient) -> str:
    """Create some public-visibility facts and set a slug. Returns the persona id."""
    await client.post("/persona/skills", json={"name": "Python", "visibility": "public"})
    await client.post("/persona/skills", json={"name": "FastAPI", "visibility": "public"})
    await client.post(
        "/persona/experiences",
        json={"role": "Backend Engineer", "company": "Acme", "visibility": "public"},
    )
    # Set slug
    await client.patch("/persona", json={"slug": "janedoe", "full_name": "Jane Doe"})
    persona = (await client.get("/persona")).json()
    return persona["id"]


async def test_public_persona_by_id(client: AsyncClient, auth_client: AsyncClient) -> None:
    pid = await _seed(auth_client)
    resp = await client.get(f"/public/personas/{pid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Jane Doe"
    assert len(body["skills"]) == 2


async def test_public_persona_by_slug(client: AsyncClient, auth_client: AsyncClient) -> None:
    await _seed(auth_client)
    resp = await client.get("/public/personas/janedoe")
    assert resp.status_code == 200
    assert resp.json()["slug"] == "janedoe"
    assert resp.json()["name"] == "Jane Doe"


async def test_public_persona_not_found(client: AsyncClient) -> None:
    resp = await client.get("/public/personas/nonexistent")
    assert resp.status_code == 404


async def test_public_ask(client: AsyncClient, auth_client: AsyncClient) -> None:
    await _seed(auth_client)
    resp = await client.post(
        "/public/personas/janedoe/ask",
        json={"question": "What skills does Jane have?"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "answer" in body
    assert body["persona_name"] == "Jane Doe"


async def test_slug_update(auth_client: AsyncClient) -> None:
    await auth_client.patch("/persona", json={"slug": "myslug"})
    persona = (await auth_client.get("/persona")).json()
    assert persona["slug"] == "myslug"
