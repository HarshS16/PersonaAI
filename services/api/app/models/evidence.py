"""Evidence: provenance for persona facts (SRD §9, §25, §48).

Every important persona fact can have one or more evidence rows. Evidence points
at a fact via (entity_type, entity_id) and, when it comes from an ingested
source, at that source and the specific chunk. Manual entries produce
user-confirmed evidence with no source.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.enums import (
    EntityType,
    EntityTypeType,
    EvidenceState,
    EvidenceStateType,
)
from app.models.mixins import UUIDPrimaryKeyMixin


class Evidence(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "evidence"

    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    entity_type: Mapped[EntityType] = mapped_column(EntityTypeType, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)

    # Set when evidence derives from an ingested source. No FK yet: the sources
    # and chunks tables are introduced in M3; the FK is added then.
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    content: Mapped[str | None] = mapped_column(String, nullable=True)  # the supporting quote
    locator: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    state: Mapped[EvidenceState] = mapped_column(
        EvidenceStateType, default=EvidenceState.user_confirmed, nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
