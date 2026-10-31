"""Schemas for the query API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

QueryEntityType = Literal[
    "project",
    "person",
    "task",
    "commitment",
    "decision",
    "risk",
    "document",
    "memory",
]


class QueryRequest(BaseModel):
    """Request payload for grounded knowledge queries."""

    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)

    project_id: UUID | None = None
    document_id: UUID | None = None
    source_type: str | None = None

    # Explicit valid-time instant for historical retrieval. A timezone is
    # required because a naive datetime does not identify an unambiguous instant.
    as_of: datetime | None = None

    # Graph context is opt-in and requires a concrete seed entity.
    entity_type: QueryEntityType | None = None
    entity_id: UUID | None = None

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

    @field_validator("as_of")
    @classmethod
    def validate_as_of(cls, value: datetime | None) -> datetime | None:
        """Require timezone-aware timestamps for historical instant queries."""

        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("as_of must be timezone-aware.")
        return value

    @model_validator(mode="after")
    def validate_entity_reference(self) -> QueryRequest:
        """Require both parts of an explicit graph seed reference."""

        if (self.entity_type is None) != (self.entity_id is None):
            raise ValueError("entity_type and entity_id must be provided together.")
        return self


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
    status: str
    valid_from: datetime | None
    valid_until: datetime | None
    confidence: float | None
    sources: list[QueryMemorySourceResponse]


class QueryRelationshipSourceResponse(BaseModel):
    """Document provenance supporting a knowledge relationship."""

    citation_id: str
    chunk_id: UUID
    document_id: UUID
    document_title: str
    content: str


class QueryRelationshipResponse(BaseModel):
    """Knowledge relationship included as query evidence."""

    citation_id: str
    relationship_id: UUID
    source_type: str
    source_id: UUID
    source_label: str
    relationship_type: str
    target_type: str
    target_id: UUID
    target_label: str
    valid_from: datetime | None
    valid_until: datetime | None
    sources: list[QueryRelationshipSourceResponse]


class QueryResponse(BaseModel):
    """Grounded query API response."""

    query: str
    answer: str
    sources: list[QuerySourceResponse]
    memories: list[QueryMemoryResponse] = Field(default_factory=list)
    relationships: list[QueryRelationshipResponse] = Field(default_factory=list)
    model: str | None
    latency_ms: float | None
    truncated: bool
