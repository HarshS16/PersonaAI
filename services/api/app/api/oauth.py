"""OAuth login + account linking for GitHub and Google.

Flow (same-origin via the Next proxy, so cookies stay first-party):
  GET  /auth/{provider}/login     -> 302 to the provider, sets a signed state cookie
  GET  /auth/{provider}/callback  -> exchanges code, upserts user + oauth_account,
                                      issues our own tokens, 302 to the frontend

The provider access token is Fernet-encrypted and stored server-side; it is
never returned to the browser (SRD §36). For GitHub this token is reused by the
M4 connector to read repositories.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import jwt
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import set_auth_cookies
from app.core.config import settings
from app.core.db import get_session
from app.core.errors import AppError
from app.core.logging import get_logger
from app.core.security import encrypt_secret
from app.domain import auth as auth_svc
from app.models.user import OAuthAccount, OAuthProvider, User

log = get_logger("oauth")
router = APIRouter(prefix="/auth", tags=["oauth"])

STATE_COOKIE = "pa_oauth_state"
FRONTEND_URL = settings.cors_origin_list[0] if settings.cors_origin_list else "http://localhost:3000"


@dataclass(frozen=True)
class ProviderConfig:
    name: OAuthProvider
    authorize_url: str
    token_url: str
    userinfo_url: str
    scopes: str
    client_id: str
    client_secret: str
    redirect_uri: str
    use_pkce: bool


def _provider(name: str) -> ProviderConfig:
    if name == "github":
        return ProviderConfig(
            name=OAuthProvider.github,
            authorize_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",
            userinfo_url="https://api.github.com/user",
            scopes="read:user user:email",
            client_id=settings.github_client_id,
            client_secret=settings.github_client_secret,
            redirect_uri=settings.github_redirect_uri,
            use_pkce=False,
        )
    if name == "google":
        return ProviderConfig(
            name=OAuthProvider.google,
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
            scopes="openid email profile",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            redirect_uri=settings.google_redirect_uri,
            use_pkce=True,
        )
    raise AppError("Unknown OAuth provider", code="unknown_provider", status_code=404)


def _sign_state(data: dict[str, Any]) -> str:
    payload = {**data, "exp": int((datetime.now(UTC) + timedelta(minutes=10)).timestamp())}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _verify_state(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise AppError("Invalid OAuth state", code="invalid_state", status_code=400) from exc


@router.get("/{provider}/login")
async def oauth_login(provider: str) -> RedirectResponse:
    cfg = _provider(provider)
    if not cfg.client_id:
        raise AppError(
            f"{provider} OAuth is not configured",
            code="provider_not_configured",
            status_code=503,
        )

    csrf = secrets.token_urlsafe(16)
    state_payload: dict[str, Any] = {"csrf": csrf, "provider": provider}
    params: dict[str, str] = {
        "client_id": cfg.client_id,
        "redirect_uri": cfg.redirect_uri,
        "scope": cfg.scopes,
        "state": csrf,
        "response_type": "code",
    }

    if cfg.use_pkce:
        verifier = secrets.token_urlsafe(64)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        params["code_challenge"] = challenge
        params["code_challenge_method"] = "S256"
        params["access_type"] = "offline"
        state_payload["verifier"] = verifier

    url = httpx.URL(cfg.authorize_url, params=params)
    resp = RedirectResponse(str(url), status_code=302)
    resp.set_cookie(
        STATE_COOKIE,
        _sign_state(state_payload),
        max_age=600,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path="/",
    )
    return resp


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    request: Request,
    code: str = Query(default=""),
    state: str = Query(default=""),
    error: str = Query(default=""),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    cfg = _provider(provider)

    if error:
        return RedirectResponse(f"{FRONTEND_URL}/login?error={error}", status_code=302)

    state_cookie = request.cookies.get(STATE_COOKIE)
    if not state_cookie or not code:
        raise AppError("Missing OAuth state or code", code="oauth_bad_request", status_code=400)
    state_data = _verify_state(state_cookie)
    if state_data.get("csrf") != state or state_data.get("provider") != provider:
        raise AppError("OAuth state mismatch", code="oauth_state_mismatch", status_code=400)

    token_data = await _exchange_code(cfg, code, state_data.get("verifier"))
    access_token = token_data.get("access_token")
    if not access_token:
        raise AppError("OAuth token exchange failed", code="oauth_exchange_failed", status_code=400)

    profile = await _fetch_profile(cfg, access_token)
    user = await _upsert_oauth_user(session, cfg, profile, token_data)

    our_access, our_refresh = await auth_svc.issue_tokens(
        session, user, user_agent=request.headers.get("user-agent")
    )
    resp = RedirectResponse(f"{FRONTEND_URL}/dashboard", status_code=302)
    set_auth_cookies(resp, our_access, our_refresh)
    resp.delete_cookie(STATE_COOKIE, path="/")
    return resp


async def _exchange_code(cfg: ProviderConfig, code: str, verifier: str | None) -> dict[str, Any]:
    data = {
        "client_id": cfg.client_id,
        "client_secret": cfg.client_secret,
        "code": code,
        "redirect_uri": cfg.redirect_uri,
        "grant_type": "authorization_code",
    }
    if verifier:
        data["code_verifier"] = verifier
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(cfg.token_url, data=data, headers={"Accept": "application/json"})
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]


async def _fetch_profile(cfg: ProviderConfig, access_token: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(cfg.userinfo_url, headers=headers)
        resp.raise_for_status()
        profile: dict[str, Any] = resp.json()
        # GitHub may hide the primary email on /user; fetch it explicitly.
        if cfg.name == OAuthProvider.github and not profile.get("email"):
            emails = await client.get("https://api.github.com/user/emails", headers=headers)
            if emails.status_code == 200:
                primary = next(
                    (e for e in emails.json() if e.get("primary") and e.get("verified")), None
                )
                if primary:
                    profile["email"] = primary["email"]
        return profile


def _normalize_profile(cfg: ProviderConfig, profile: dict[str, Any]) -> tuple[str, str, str | None]:
    """Return (provider_user_id, email, username)."""
    if cfg.name == OAuthProvider.github:
        return str(profile["id"]), profile.get("email", ""), profile.get("login")
    # Google / OIDC
    return str(profile["sub"]), profile.get("email", ""), profile.get("name")


async def _upsert_oauth_user(
    session: AsyncSession,
    cfg: ProviderConfig,
    profile: dict[str, Any],
    token_data: dict[str, Any],
) -> User:
    provider_user_id, email, username = _normalize_profile(cfg, profile)
    email = (email or "").lower().strip()

    # 1. Existing oauth_account?
    result = await session.execute(
        select(OAuthAccount).where(
            OAuthAccount.provider == cfg.name,
            OAuthAccount.provider_user_id == provider_user_id,
        )
    )
    account = result.scalar_one_or_none()

    if account is not None:
        user = await session.get(User, account.user_id)
        assert user is not None
    else:
        # 2. Link to an existing user by email, else create one.
        user = None
        if email:
            res = await session.execute(select(User).where(User.email == email))
            user = res.scalar_one_or_none()
        if user is None:
            if not email:
                raise AppError(
                    "Provider did not supply an email", code="oauth_no_email", status_code=400
                )
            user = User(email=email, name=username, email_verified=True)
            session.add(user)
            await session.flush()
        account = OAuthAccount(
            user_id=user.id,
            provider=cfg.name,
            provider_user_id=provider_user_id,
        )
        session.add(account)

    # Refresh stored tokens + metadata.
    account.provider_username = username
    account.scopes = cfg.scopes
    if token_data.get("access_token"):
        account.access_token_enc = encrypt_secret(token_data["access_token"])
    if token_data.get("refresh_token"):
        account.refresh_token_enc = encrypt_secret(token_data["refresh_token"])
    await session.flush()
    return user
