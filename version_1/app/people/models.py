from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class PersonSource(BaseModel):
    """Source location supporting a persisted person."""

    chunk_id: UUID


class Person(BaseModel):
    """Persisted person representation."""

    id: UUID
    user_id: UUID
    name: str = Field(min_length=1)
    email: str | None = None
    sources: list[PersonSource] = Field(min_length=1)