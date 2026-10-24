"""Database-backed evaluation of personal-memory retrieval."""

from uuid import uuid4

import pytest
from app.database.models.memory import Memory
from app.database.models.user import User
from app.evaluation.memory import MemoryRetrievalEvaluator
from app.memory.service import MemoryService
from tests.evaluation.memory_dataset import (
    MEMORY_EVALUATION_CASES,
    MEMORY_FIXTURES,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_memory_retrieval_evaluation(db_session) -> None:
    """Evaluate memory retrieval against a deterministic labelled dataset."""
    user = User(
        email=f"memory-evaluation-{uuid4()}@pais.local",
        display_name="Memory Evaluation User",
    )
    db_session.add(user)
    await db_session.flush()

    for fixture in MEMORY_FIXTURES:
        db_session.add(
            Memory(
                id=fixture.id,
                user_id=user.id,
                memory_type=fixture.memory_type,
                content=fixture.content,
                normalized_content=" ".join(fixture.content.casefold().split()),
                status="active",
                confidence=fixture.confidence,
            )
        )

    await db_session.flush()

    evaluator = MemoryRetrievalEvaluator(memory_service=MemoryService())

    result = await evaluator.evaluate(
        db_session,
        list(MEMORY_EVALUATION_CASES),
        user_id=user.id,
        k=3,
    )

    assert 0.0 <= result.recall_at_k <= 1.0
    assert 0.0 <= result.mrr <= 1.0
    assert 0.0 <= result.ndcg_at_k <= 1.0

    # Every labelled query has at least one relevant memory.
    # A zero score would indicate a retrieval or ranking failure
    # across the entire evaluation set.
    assert result.recall_at_k > 0.0
    assert result.mrr > 0.0
    assert result.ndcg_at_k > 0.0

    print(
        "\nMemory retrieval evaluation"
        f"\nCases: {len(MEMORY_EVALUATION_CASES)}"
        "\nK: 3"
        f"\nRecall@3: {result.recall_at_k:.4f}"
        f"\nMRR: {result.mrr:.4f}"
        f"\nNDCG@3: {result.ndcg_at_k:.4f}"
    )
