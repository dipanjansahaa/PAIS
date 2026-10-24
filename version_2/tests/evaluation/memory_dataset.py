"""Deterministic labelled dataset for memory retrieval evaluation."""

from dataclasses import dataclass
from uuid import UUID

from app.evaluation.cases import MemoryEvaluationCase


@dataclass(frozen=True)
class MemoryFixture:
    """A memory record used to seed the evaluation database."""

    id: UUID
    memory_type: str
    content: str
    confidence: float = 0.9


MEMORY_FIXTURES = (
    MemoryFixture(
        id=UUID("10000000-0000-4000-8000-000000000001"),
        memory_type="preference",
        content="I prefer Python for backend development.",
    ),
    MemoryFixture(
        id=UUID("10000000-0000-4000-8000-000000000002"),
        memory_type="preference",
        content="I prefer TypeScript for frontend development.",
    ),
    MemoryFixture(
        id=UUID("10000000-0000-4000-8000-000000000003"),
        memory_type="goal",
        content="My goal is to build a personal AI assistant using RAG.",
    ),
    MemoryFixture(
        id=UUID("10000000-0000-4000-8000-000000000004"),
        memory_type="constraint",
        content="I want to host my projects on free-tier infrastructure.",
    ),
    MemoryFixture(
        id=UUID("10000000-0000-4000-8000-000000000005"),
        memory_type="fact",
        content="I work with SAP ABAP development.",
    ),
    MemoryFixture(
        id=UUID("10000000-0000-4000-8000-000000000006"),
        memory_type="goal",
        content="I want to learn cloud architecture.",
    ),
    MemoryFixture(
        id=UUID("10000000-0000-4000-8000-000000000007"),
        memory_type="preference",
        content="I prefer concise technical documentation.",
    ),
    MemoryFixture(
        id=UUID("10000000-0000-4000-8000-000000000008"),
        memory_type="fact",
        content="PAIS uses PostgreSQL and pgvector for data storage and retrieval.",
    ),
    MemoryFixture(
        id=UUID("10000000-0000-4000-8000-000000000009"),
        memory_type="fact",
        content="I enjoy cycling during weekends.",
    ),
)


def _case(
    query: str,
    grades: dict[int, int],
) -> MemoryEvaluationCase:
    """Build a labelled case using fixture numbers as stable references."""

    relevance = {MEMORY_FIXTURES[index - 1].id: grade for index, grade in grades.items()}

    return MemoryEvaluationCase(
        query=query,
        relevant_ids=set(relevance),
        relevance=relevance,
    )


MEMORY_EVALUATION_CASES = (
    _case(
        "Python backend development",
        {1: 3},
    ),
    _case(
        "TypeScript frontend development",
        {2: 3},
    ),
    _case(
        "personal AI assistant RAG project",
        {3: 3, 8: 1},
    ),
    _case(
        "free hosting infrastructure constraint",
        {4: 3},
    ),
    _case(
        "SAP ABAP development work",
        {5: 3},
    ),
    _case(
        "cloud architecture learning goal",
        {6: 3},
    ),
    _case(
        "concise technical documentation preference",
        {7: 3},
    ),
    _case(
        "PAIS PostgreSQL pgvector storage retrieval",
        {8: 3},
    ),
)
