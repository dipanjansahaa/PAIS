"""Domain models for tasks."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class TaskStatus(StrEnum):
    """Lifecycle states supported by a task."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskSource(BaseModel):
    """Source reference supporting a task."""

    chunk_id: UUID


class Task(BaseModel):
    """Application-level task state derived from structured intelligence."""

    id: UUID
    user_id: UUID
    project_id: UUID | None = None
    commitment_id: UUID | None = None
    description: str = Field(min_length=1)
    owner: str | None = None
    due_at: datetime | None = None
    priority: str | None = None
    status: TaskStatus = TaskStatus.OPEN
    sources: list[TaskSource] = Field(min_length=1)
