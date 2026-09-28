"""Schemas for search API."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class SearchRequest(BaseModel):
    """Request payload for document search."""

    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)

    project_id: UUID | None = None
    document_id: UUID | None = None
    source_type: str | None = None

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        """Normalize and validate the search query."""
        value = value.strip()

        if not value:
            raise ValueError("Query must not be empty.")

        return value


class SearchResultResponse(BaseModel):
    """Single search result returned by the API."""

    chunk_id: UUID
    document_id: UUID
    content: str
    score: float


class SearchResponse(BaseModel):
    """Search API response."""

    query: str
    results: list[SearchResultResponse]