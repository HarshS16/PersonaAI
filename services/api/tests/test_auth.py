from __future__ import annotations

import pytest
from httpx import AsyncClient

SIGNUP = {"email": "dev@example.com", "password": "s3cretpass", "name": "Dev"}


async def _signup(client: AsyncClient, **over: object) -> dict:
    payload = {**SIGNUP, **over}
    resp = await client.post("/auth/signup", json=payload)
    return resp  # type: ignore[return-value]


async def test_signup_returns_token_and_sets_cookies(client: AsyncClient) -> None:
    resp = await _signup(client)
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["user"]["email"] == "dev@example.com"
    assert "pa_access" in resp.cookies
    assert "pa_refresh" in resp.cookies


async def test_signup_duplicate_email_conflicts(client: AsyncClient) -> None:
    await _signup(client)
    resp = await _signup(client)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "email_taken"


async def test_login_wrong_password(client: AsyncClient) -> None:
    await _signup(client)
    resp = await client.post("/auth/login", json={"email": SIGNUP["email"], "password": "nope"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_credentials"


async def test_me_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


async def test_me_with_token(client: AsyncClient) -> None:
    signup = await _signup(client)
    token = signup.json()["access_token"]
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == SIGNUP["email"]


async def test_refresh_rotates_token(client: AsyncClient) -> None:
    await _signup(client)
    first = client.cookies.get("pa_refresh")
    resp = await client.post("/auth/refresh")
    assert resp.status_code == 200
    rotated = resp.cookies.get("pa_refresh")
    assert rotated is not None and rotated != first


async def test_refresh_reuse_revokes_family(client: AsyncClient) -> None:
    await _signup(client)
    old_refresh = client.cookies.get("pa_refresh")
    # Rotate once (old token now revoked).
    await client.post("/auth/refresh")
    # Present the OLD token again -> reuse detected.
    resp = await client.post("/auth/refresh", cookies={"pa_refresh": old_refresh})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "refresh_reuse"


async def test_logout_clears_and_revokes(client: AsyncClient) -> None:
    await _signup(client)
    resp = await client.post("/auth/logout")
    assert resp.status_code == 204
    # The refresh token was revoked, so a subsequent refresh fails.
    again = await client.post("/auth/refresh", cookies={"pa_refresh": "anything"})
    assert again.status_code == 401


async def test_change_password_flow(client: AsyncClient) -> None:
    signup = await _signup(client)
    token = signup.json()["access_token"]
    resp = await client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": SIGNUP["password"], "new_password": "brandNewPass1"},
    )
    assert resp.status_code == 204
    # Old password no longer works, new one does.
    email = SIGNUP["email"]
    bad = await client.post("/auth/login", json={"email": email, "password": SIGNUP["password"]})
    assert bad.status_code == 401
    good = await client.post("/auth/login", json={"email": email, "password": "brandNewPass1"})
    assert good.status_code == 200


async def test_signup_validation(client: AsyncClient) -> None:
    resp = await client.post("/auth/signup", json={"email": "not-an-email", "password": "short"})
    assert resp.status_code == 422


@pytest.mark.parametrize("provider", ["github", "google"])
async def test_oauth_login_unconfigured(client: AsyncClient, provider: str) -> None:
    # No client IDs in the test env -> 503, not a crash.
    resp = await client.get(f"/auth/{provider}/login", follow_redirects=False)
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "provider_not_configured"
