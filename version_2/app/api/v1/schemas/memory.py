"""Request and response schemas for personal memory management."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


MemoryType = Literal["fact", "preference", "goal", "constraint"]
MemoryStatus = Literal["active", "superseded", "expired"]


class MemorySourceResponse(BaseModel):
    """Provenance attached to a memory."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_kind: str
    document_id: UUID | None
    chunk_id: UUID | None
    source_reference: str | None
    evidence_text: str | None
    created_at: datetime


class MemoryResponse(BaseModel):
    """A persisted memory and its lifecycle metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    memory_type: MemoryType
    content: str
    status: MemoryStatus
    confidence: float | None
    valid_from: datetime | None
    valid_until: datetime | None
    last_confirmed_at: datetime | None
    supersedes_id: UUID | None
    created_at: datetime
    updated_at: datetime
    sources: list[MemorySourceResponse] = Field(default_factory=list)


class MemoryListResponse(BaseModel):
    """Paginated memories for the authenticated user."""

    items: list[MemoryResponse]
    limit: int
    offset: int


class MemoryCorrectionRequest(BaseModel):
    """Fields accepted when correcting an active memory."""

    content: str = Field(min_length=1, max_length=20_000)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    source_reference: str | None = Field(default=None, max_length=4_000)
    evidence_text: str | None = Field(default=None, max_length=20_000)