"""One-time token issuance/consumption for email verification and password reset."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthError
from app.core.security import generate_url_token, hash_token
from app.models.user import OneTimeToken, TokenPurpose, User

_TTL = {
    TokenPurpose.email_verification: timedelta(days=2),
    TokenPurpose.password_reset: timedelta(hours=1),
}


async def issue_token(session: AsyncSession, user: User, purpose: TokenPurpose) -> str:
    plain = generate_url_token()
    ott = OneTimeToken(
        user_id=user.id,
        purpose=purpose,
        token_hash=hash_token(plain),
        expires_at=datetime.now(UTC) + _TTL[purpose],
    )
    session.add(ott)
    await session.flush()
    return plain


async def consume_token(session: AsyncSession, plain: str, purpose: TokenPurpose) -> User:
    result = await session.execute(
        select(OneTimeToken).where(
            OneTimeToken.token_hash == hash_token(plain),
            OneTimeToken.purpose == purpose,
        )
    )
    ott = result.scalar_one_or_none()
    now = datetime.now(UTC)
    if ott is None or ott.used_at is not None or ott.expires_at <= now:
        raise AuthError("Invalid or expired token", code="invalid_token")
    ott.used_at = now
    user = await session.get(User, ott.user_id)
    if user is None:
        raise AuthError("User no longer exists")
    return user
