from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class RiskSource(BaseModel):
    chunk_id: UUID


class Risk(BaseModel):
    id: UUID
    user_id: UUID
    title: str = Field(min_length=1)
    description: str | None = None
    severity: str | None = None
    sources: list[RiskSource] = Field(min_length=1)