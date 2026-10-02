"""Domain models for LLM observability."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class ModelRunOperation(StrEnum):
    """Application operations that invoke an LLM."""

    QUERY = "query"
    DAILY_GENERATION = "daily_generation"
    STRUCTURED_INTELLIGENCE = "structured_intelligence"


class ModelRunStatus(StrEnum):
    """Execution status of an LLM model run."""

    COMPLETED = "completed"
    FAILED = "failed"


class ModelRun(BaseModel):
    """Observable metadata for one LLM invocation."""

    id: UUID
    user_id: UUID
    operation: ModelRunOperation
    status: ModelRunStatus
    provider: str = Field(min_length=1)
    model: str | None = None
    temperature: float = Field(ge=0.0)
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    latency_ms: float = Field(ge=0.0)
    finish_reason: str | None = None
    started_at: datetime
    completed_at: datetime
    error_type: str | None = None