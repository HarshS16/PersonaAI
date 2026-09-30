"""Auth request/response DTOs."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class UpdateProfileRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)


class OAuthAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str
    provider_username: str | None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str | None
    role: str
    email_verified: bool
    created_at: datetime


class MeOut(UserOut):
    oauth_accounts: list[OAuthAccountOut] = []


class TokenOut(BaseModel):
    """Access token returned in the body; refresh token is set as an httpOnly cookie."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
