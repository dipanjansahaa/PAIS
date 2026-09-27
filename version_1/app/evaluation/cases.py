from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RetrievalEvaluationCase:
    query: str
    relevant_ids: set[UUID]
    relevance: dict[UUID, int]