"""Async SQLAlchemy engine, session factory, and declarative base."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Declarative base. Concrete mixins live in app.models.mixins."""


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a request-scoped session."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


# Re-export for convenience in models.
__all__ = ["Base", "SessionLocal", "engine", "get_session", "new_uuid", "DateTime", "func"]

_ = (datetime, mapped_column, Mapped)  # keep imports for model modules
