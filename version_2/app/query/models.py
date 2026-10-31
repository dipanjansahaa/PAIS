"""Models used by the query application service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.query.context import ContextSource
from app.query.relationship_context import QueryRelationship


@dataclass(frozen=True, slots=True)
class QueryMemorySource:
    """Provenance for a memory used during query answering."""

    source_kind: str
    document_id: str | None
    chunk_id: str | None
    source_reference: str | None
    evidence_text: str | None


@dataclass(frozen=True, slots=True)
class QueryMemory:
    """A personal memory included in query context."""

    citation_id: str
    memory_id: str
    memory_type: str
    content: str
    status: str
    valid_from: datetime | None
    valid_until: datetime | None
    confidence: float | None
    sources: tuple[QueryMemorySource, ...]


@dataclass(frozen=True, slots=True)
class QueryResult:
    """Final internal result produced by QueryService."""

    query: str
    answer: str
    sources: tuple[ContextSource, ...]
    model: str | None
    latency_ms: float | None
    truncated: bool
    memories: tuple[QueryMemory, ...] = ()
    relationships: tuple[QueryRelationship, ...] = ()
