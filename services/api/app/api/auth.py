"""Email/password auth endpoints: signup, login, refresh, logout, password
reset, email verification, and account management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    REFRESH_COOKIE,
    clear_auth_cookies,
    get_current_user,
    set_auth_cookies,
)
from app.core.config import settings
from app.core.db import get_session
from app.core.email import send_email
from app.core.errors import AuthError
from app.core.ratelimit import limiter
from app.core.security import hash_password, verify_password
from app.domain import auth as auth_svc
from app.domain import tokens as token_svc
from app.models.user import TokenPurpose, User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MeOut,
    ResetPasswordRequest,
    SignupRequest,
    TokenOut,
    UpdateProfileRequest,
    UserOut,
    VerifyEmailRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])

FRONTEND_URL = settings.cors_origin_list[0] if settings.cors_origin_list else "http://localhost:3000"


def _token_response(response: Response, access: str, refresh: str, user: User) -> TokenOut:
    set_auth_cookies(response, access, refresh)
    return TokenOut(
        access_token=access,
        expires_in=auth_svc.access_ttl_seconds(),
        user=UserOut.model_validate(user),
    )


@router.post("/signup", response_model=TokenOut)
@limiter.limit("10/hour")
async def signup(
    request: Request,
    body: SignupRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> TokenOut:
    user = await auth_svc.create_user(
        session, email=body.email, password=body.password, name=body.name
    )
    verify_token = await token_svc.issue_token(session, user, TokenPurpose.email_verification)
    send_email(
        user.email,
        "Verify your PersonaAI email",
        "Welcome to PersonaAI! Verify your email:\n\n"
        f"{FRONTEND_URL}/verify-email?token={verify_token}",
    )
    access, refresh = await auth_svc.issue_tokens(
        session, user, user_agent=request.headers.get("user-agent")
    )
    return _token_response(response, access, refresh, user)


@router.post("/login", response_model=TokenOut)
@limiter.limit("20/minute")
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> TokenOut:
    user = await auth_svc.authenticate(session, email=body.email, password=body.password)
    access, refresh = await auth_svc.issue_tokens(
        session, user, user_agent=request.headers.get("user-agent")
    )
    return _token_response(response, access, refresh, user)


@router.post("/refresh", response_model=TokenOut)
async def refresh(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> TokenOut:
    refresh_plain = request.cookies.get(REFRESH_COOKIE)
    if not refresh_plain:
        raise AuthError("No refresh token", code="no_refresh")
    access, new_refresh, user = await auth_svc.rotate_refresh_token(
        session, refresh_plain, user_agent=request.headers.get("user-agent")
    )
    return _token_response(response, access, new_refresh, user)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> Response:
    refresh_plain = request.cookies.get(REFRESH_COOKIE)
    if refresh_plain:
        await auth_svc.revoke_refresh_token(session, refresh_plain)
    clear_auth_cookies(response)
    response.status_code = 204
    return response


@router.get("/me", response_model=MeOut)
async def me(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MeOut:
    # Eager-load oauth_accounts so serialization does not trigger lazy IO.
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    result = await session.execute(
        select(User).where(User.id == user.id).options(selectinload(User.oauth_accounts))
    )
    full = result.scalar_one()
    return MeOut.model_validate(full)


@router.patch("/me", response_model=UserOut)
async def update_profile(
    body: UpdateProfileRequest,
    user: User = Depends(get_current_user),
) -> UserOut:
    if body.name is not None:
        user.name = body.name
    return UserOut.model_validate(user)


@router.post("/forgot-password", status_code=202)
@limiter.limit("5/hour")
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    from app.api.deps import get_user_by_email

    user = await get_user_by_email(session, body.email)
    # Always return 202 so the endpoint doesn't reveal which emails exist.
    if user is not None:
        reset_token = await token_svc.issue_token(session, user, TokenPurpose.password_reset)
        send_email(
            user.email,
            "Reset your PersonaAI password",
            f"Reset your password:\n\n{FRONTEND_URL}/reset-password?token={reset_token}",
        )
    return {"status": "accepted"}


@router.post("/reset-password", status_code=204)
async def reset_password(
    body: ResetPasswordRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> Response:
    user = await token_svc.consume_token(session, body.token, TokenPurpose.password_reset)
    user.password_hash = hash_password(body.password)
    # Resetting the password revokes all existing sessions.
    await auth_svc.revoke_all_sessions(session, user)
    response.status_code = 204
    return response


@router.post("/verify-email", status_code=204)
async def verify_email(
    body: VerifyEmailRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> Response:
    user = await token_svc.consume_token(session, body.token, TokenPurpose.email_verification)
    user.email_verified = True
    response.status_code = 204
    return response


@router.post("/change-password", status_code=204)
async def change_password(
    body: ChangePasswordRequest,
    response: Response,
    user: User = Depends(get_current_user),
) -> Response:
    if user.password_hash is None or not verify_password(body.current_password, user.password_hash):
        raise AuthError("Current password is incorrect", code="invalid_credentials")
    user.password_hash = hash_password(body.new_password)
    response.status_code = 204
    return response
