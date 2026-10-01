from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectStatus(StrEnum):
    """Lifecycle status for a project."""

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ProjectSource(BaseModel):
    """Source location supporting a persisted project."""

    chunk_id: UUID


class Project(BaseModel):
    """Persisted project representation."""

    id: UUID
    user_id: UUID
    name: str = Field(min_length=1)
    description: str | None = None
    status: ProjectStatus = ProjectStatus.ACTIVE
    sources: list[ProjectSource] = Field(min_length=1)