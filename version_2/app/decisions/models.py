"""Domain models for decisions and provenance."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class DecisionStatus(StrEnum):
    """Lifecycle states supported by a decision."""

    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REVERSED = "reversed"


class DecisionSource(BaseModel):
    """Source reference supporting a decision."""

    chunk_id: UUID


class Decision(BaseModel):
    """Application-level decision derived from structured intelligence."""

    id: UUID
    user_id: UUID
    project_id: UUID | None = None
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    decision_date: datetime | None = None
    status: DecisionStatus = DecisionStatus.ACTIVE
    sources: list[DecisionSource] = Field(min_length=1)