"""Schemas for the query API."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class QueryRequest(BaseModel):
    """Request payload for grounded knowledge queries."""

    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)

    project_id: UUID | None = None
    document_id: UUID | None = None
    source_type: str | None = None

    temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        """Normalize and validate the query."""
        value = value.strip()

        if not value:
            raise ValueError("Query must not be empty.")

        return value


class QueryChunkResponse(BaseModel):
    """Retrieved chunk used as grounding context."""

    citation_id: str
    chunk_id: UUID
    document_id: UUID
    content: str
    score: float
    metadata: dict | None


class QuerySourceResponse(BaseModel):
    """Source document represented by its retrieved chunks."""

    citation_id: str
    document_id: UUID
    chunks: list[QueryChunkResponse]


class QueryResponse(BaseModel):
    """Grounded query API response."""

    query: str
    answer: str
    sources: list[QuerySourceResponse]
    model: str | None
    latency_ms: float | None
    truncated: bool