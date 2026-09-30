"""Shared FastAPI dependencies: current user, role guards, cookie helpers."""

from __future__ import annotations

import uuid

import jwt
from fastapi import Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_session
from app.core.errors import AuthError, ForbiddenError
from app.core.security import decode_access_token
from app.models.user import Role, User

ACCESS_COOKIE = "pa_access"
REFRESH_COOKIE = "pa_refresh"


def _bearer_token(request: Request) -> str | None:
    auth = request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth[7:]
    return request.cookies.get(ACCESS_COOKIE)


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    token = _bearer_token(request)
    if not token:
        raise AuthError("Not authenticated")
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Token expired", code="token_expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid token") from exc

    user = await session.get(User, uuid.UUID(payload["sub"]))
    if user is None:
        raise AuthError("User no longer exists")
    return user


def require_role(*roles: Role):  # type: ignore[no-untyped-def]
    async def _guard(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise ForbiddenError("Insufficient permissions")
        return user

    return _guard


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    secure = settings.is_production
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=settings.access_token_ttl_minutes * 60,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=settings.refresh_token_ttl_days * 24 * 3600,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()
