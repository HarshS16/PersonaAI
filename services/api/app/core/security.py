"""Cryptographic primitives: password hashing, JWTs, opaque-token hashing,
and symmetric encryption for third-party OAuth tokens stored at rest.

Design notes:
- Access tokens are short-lived JWTs (stateless).
- Refresh tokens are long, opaque, random strings. Only their SHA-256 hash is
  stored, so a DB leak does not expose usable tokens. They rotate on every use
  and carry a `family` id so that reuse of a revoked token revokes the family.
- OAuth provider tokens are Fernet-encrypted; the plaintext never leaves the
  backend and is never serialized to API responses (SRD §36).
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet

from app.core.config import settings

_ph = PasswordHasher()
_ALGO = "HS256"


# ---- Passwords ----
def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        _ph.verify(password_hash, password)
        return True
    except VerifyMismatchError:
        return False


def needs_rehash(password_hash: str) -> bool:
    return _ph.check_needs_rehash(password_hash)


# ---- JWT access tokens ----
TokenType = Literal["access"]


def create_access_token(subject: str, *, extra: dict[str, Any] | None = None) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_ttl_minutes)).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGO)


def decode_access_token(token: str) -> dict[str, Any]:
    """Raises jwt.PyJWTError subclasses on invalid/expired tokens."""
    payload: dict[str, Any] = jwt.decode(token, settings.jwt_secret, algorithms=[_ALGO])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("wrong token type")
    return payload


# ---- Opaque refresh tokens ----
def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """One-way hash for storing refresh/reset/verification tokens."""
    return hashlib.sha256(token.encode()).hexdigest()


def generate_url_token() -> str:
    """For email verification / password reset links."""
    return secrets.token_urlsafe(32)


def refresh_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days)


# ---- Fernet encryption for OAuth tokens ----
def _fernet() -> Fernet:
    return Fernet(settings.encryption_key.encode())


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()
