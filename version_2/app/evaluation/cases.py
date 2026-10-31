from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RetrievalEvaluationCase:
    query: str
    relevant_ids: set[UUID]
    relevance: dict[UUID, int]


@dataclass(frozen=True)
class MemoryEvaluationCase:
    """A labelled query used to evaluate personal-memory retrieval."""

    query: str
    relevant_ids: set[UUID]
    relevance: dict[UUID, int]


@dataclass(frozen=True)
class RelationshipEvaluationCase:
    """A labelled seed-entity case for relationship-context evaluation."""

    entity_type: str
    entity_id: UUID
    relevant_ids: set[UUID]
    relevance: dict[UUID, int]
