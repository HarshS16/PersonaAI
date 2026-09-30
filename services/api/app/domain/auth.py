"""Auth domain logic: account creation, authentication, token issuance and
refresh-token rotation with reuse detection.

These functions operate on an AsyncSession and do not commit; the request
dependency (`get_session`) commits at the end of a successful request.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AuthError, ConflictError
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    refresh_expiry,
    verify_password,
)
from app.models.user import RefreshToken, Role, User


async def create_user(
    session: AsyncSession,
    *,
    email: str,
    password: str | None,
    name: str | None,
    email_verified: bool = False,
) -> User:
    email = email.lower().strip()
    existing = await session.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("An account with this email already exists", code="email_taken")

    user = User(
        email=email,
        name=name,
        password_hash=hash_password(password) if password else None,
        role=Role.user,
        email_verified=email_verified,
    )
    session.add(user)
    await session.flush()
    return user


async def authenticate(session: AsyncSession, *, email: str, password: str) -> User:
    result = await session.execute(select(User).where(User.email == email.lower().strip()))
    user = result.scalar_one_or_none()
    if user is None or user.password_hash is None:
        # Avoid revealing whether the email exists or is OAuth-only.
        raise AuthError("Invalid email or password", code="invalid_credentials")
    if not verify_password(password, user.password_hash):
        raise AuthError("Invalid email or password", code="invalid_credentials")
    return user


async def issue_tokens(
    session: AsyncSession,
    user: User,
    *,
    family_id: uuid.UUID | None = None,
    user_agent: str | None = None,
) -> tuple[str, str]:
    """Return (access_token, refresh_token_plaintext) and persist the refresh hash."""
    access = create_access_token(str(user.id), extra={"role": user.role.value})
    refresh_plain = generate_refresh_token()
    rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_plain),
        family_id=family_id or uuid.uuid4(),
        expires_at=refresh_expiry(),
        user_agent=(user_agent or "")[:300] or None,
    )
    session.add(rt)
    await session.flush()
    return access, refresh_plain


async def rotate_refresh_token(
    session: AsyncSession,
    refresh_plain: str,
    *,
    user_agent: str | None = None,
) -> tuple[str, str, User]:
    """Validate a refresh token, revoke it, and issue a fresh pair.

    Reuse of an already-revoked token revokes the entire family.
    """
    token_hash = hash_token(refresh_plain)
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    rt = result.scalar_one_or_none()
    if rt is None:
        raise AuthError("Invalid refresh token", code="invalid_refresh")

    now = datetime.now(UTC)
    if rt.revoked_at is not None:
        # Reuse detected: revoke the whole family.
        await _revoke_family(session, rt.family_id)
        raise AuthError("Refresh token reuse detected", code="refresh_reuse")
    if rt.expires_at <= now:
        raise AuthError("Refresh token expired", code="refresh_expired")

    rt.revoked_at = now
    user = await session.get(User, rt.user_id)
    if user is None:
        raise AuthError("User no longer exists")

    access, new_refresh = await issue_tokens(
        session, user, family_id=rt.family_id, user_agent=user_agent
    )
    return access, new_refresh, user


async def revoke_refresh_token(session: AsyncSession, refresh_plain: str) -> None:
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh_plain))
    )
    rt = result.scalar_one_or_none()
    if rt is not None and rt.revoked_at is None:
        rt.revoked_at = datetime.now(UTC)


async def revoke_all_sessions(session: AsyncSession, user: User) -> None:
    """Revoke every active refresh token for a user (e.g. on password reset)."""
    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
        )
    )
    now = datetime.now(UTC)
    for rt in result.scalars().all():
        rt.revoked_at = now


async def _revoke_family(session: AsyncSession, family_id: uuid.UUID) -> None:
    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None)
        )
    )
    for rt in result.scalars().all():
        rt.revoked_at = datetime.now(UTC)


def access_ttl_seconds() -> int:
    return settings.access_token_ttl_minutes * 60
