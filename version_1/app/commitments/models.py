"""Domain models for commitments."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class CommitmentStatus(StrEnum):
    """Lifecycle states supported by a commitment."""

    OPEN = "open"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"


class CommitmentSource(BaseModel):
    """Source reference supporting a commitment."""

    chunk_id: UUID


class Commitment(BaseModel):
    """Application-level commitment state derived from structured intelligence."""

    id: UUID
    user_id: UUID
    project_id: UUID | None = None
    description: str = Field(min_length=1)
    owner: str | None = None
    deadline_at: datetime | None = None
    status: CommitmentStatus = CommitmentStatus.OPEN
    sources: list[CommitmentSource] = Field(min_length=1)
