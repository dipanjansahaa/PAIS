"""Unit tests for personal-memory retrieval evaluation."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.evaluation.cases import MemoryEvaluationCase
from app.evaluation.memory import MemoryRetrievalEvaluator


class FakeMemoryService:
    """Return predefined results and record retrieval arguments."""

    def __init__(self, result_sets):
        self.result_sets = list(result_sets)
        self.calls = []

    async def retrieve_memories(
        self,
        session,
        *,
        user_id,
        query=None,
        memory_types=None,
        limit=10,
        as_of=None,
    ):
        self.calls.append(
            {
                "session": session,
                "user_id": user_id,
                "query": query,
                "limit": limit,
                "as_of": as_of,
            }
        )
        return self.result_sets.pop(0)


@pytest.mark.asyncio
async def test_evaluator_calculates_metrics_for_memory_results():
    user_id = uuid4()

    relevant_first = uuid4()
    irrelevant = uuid4()
    relevant_second = uuid4()
    missing_relevant = uuid4()

    cases = [
        MemoryEvaluationCase(
            query="preferred programming language",
            relevant_ids={relevant_first},
            relevance={relevant_first: 3},
        ),
        MemoryEvaluationCase(
            query="backend development preference",
            relevant_ids={relevant_second},
            relevance={relevant_second: 3},
        ),
        MemoryEvaluationCase(
            query="long-term career objective",
            relevant_ids={missing_relevant},
            relevance={missing_relevant: 3},
        ),
    ]

    service = FakeMemoryService(
        [
            [
                SimpleNamespace(id=relevant_first),
                SimpleNamespace(id=irrelevant),
            ],
            [
                SimpleNamespace(id=irrelevant),
                SimpleNamespace(id=relevant_second),
            ],
            [],
        ]
    )

    evaluator = MemoryRetrievalEvaluator(service)

    result = await evaluator.evaluate(
        object(),
        cases,
        user_id=user_id,
        k=5,
    )

    assert result.recall_at_k == pytest.approx(2 / 3)
    assert result.mrr == pytest.approx(0.5)

    assert 0.0 <= result.ndcg_at_k <= 1.0
    assert len(service.calls) == 3

    assert all(call["user_id"] == user_id for call in service.calls)
    assert [call["query"] for call in service.calls] == [case.query for case in cases]
    assert all(call["limit"] == 5 for call in service.calls)


@pytest.mark.asyncio
async def test_evaluator_forwards_as_of_timestamp():
    timestamp = datetime(2026, 10, 25, tzinfo=UTC)

    service = FakeMemoryService([[SimpleNamespace(id=uuid4())]])

    evaluator = MemoryRetrievalEvaluator(service)

    case = MemoryEvaluationCase(
        query="Python preference",
        relevant_ids=set(),
        relevance={},
    )

    await evaluator.evaluate(
        object(),
        [case],
        user_id=uuid4(),
        as_of=timestamp,
    )

    assert service.calls[0]["as_of"] == timestamp


@pytest.mark.asyncio
async def test_evaluator_rejects_empty_cases():
    evaluator = MemoryRetrievalEvaluator(FakeMemoryService([]))

    with pytest.raises(ValueError, match="At least one evaluation case"):
        await evaluator.evaluate(
            object(),
            [],
            user_id=uuid4(),
        )


@pytest.mark.parametrize("k", [0, -1, 101])
@pytest.mark.asyncio
async def test_evaluator_rejects_invalid_k(k):
    evaluator = MemoryRetrievalEvaluator(FakeMemoryService([]))

    with pytest.raises(ValueError, match="between 1 and 100"):
        await evaluator.evaluate(
            object(),
            [
                MemoryEvaluationCase(
                    query="Python preference",
                    relevant_ids=set(),
                    relevance={},
                )
            ],
            user_id=uuid4(),
            k=k,
        )
