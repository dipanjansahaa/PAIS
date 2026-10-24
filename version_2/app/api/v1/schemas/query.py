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
    """Retrieved document chunk used as grounding context."""

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


class QueryMemorySourceResponse(BaseModel):
    """Provenance attached to a memory used in an answer."""

    source_kind: str
    document_id: UUID | None
    chunk_id: UUID | None
    source_reference: str | None
    evidence_text: str | None


class QueryMemoryResponse(BaseModel):
    """Personal memory used as query evidence."""

    citation_id: str
    memory_id: UUID
    memory_type: str
    content: str
    confidence: float | None
    sources: list[QueryMemorySourceResponse]


class QueryResponse(BaseModel):
    """Grounded query API response."""

    query: str
    answer: str
    sources: list[QuerySourceResponse]
    memories: list[QueryMemoryResponse] = Field(default_factory=list)
    model: str | None
    latency_ms: float | None
    truncated: bool
