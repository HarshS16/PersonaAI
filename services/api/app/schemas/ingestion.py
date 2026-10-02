"""Ingestion DTOs: sources, jobs, conflicts."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    provider: str | None
    title: str | None
    url: str | None
    status: str
    last_synced: datetime | None
    stats: dict[str, Any]
    error: str | None
    created_at: datetime


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_id: uuid.UUID | None
    type: str
    status: str
    progress: float
    step: str | None
    error: str | None
    result: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class UploadResponse(BaseModel):
    source: SourceOut
    job: JobOut
    duplicate: bool = False


class ConflictOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    field: str
    candidates: list[dict[str, Any]]
    status: str
    resolution: dict[str, Any]
    created_at: datetime


class ResolveConflictRequest(BaseModel):
    chosen_value: str
