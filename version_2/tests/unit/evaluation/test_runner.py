"""Contract tests for the shared document retrieval evaluator."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.evaluation.cases import RetrievalEvaluationCase
from app.evaluation.runner import RetrievalEvaluator


class FakeRetriever:
    def __init__(self, result_sets):
        self.result_sets = list(result_sets)
        self.calls = []

    async def search(self, *, session, query, top_k, user_id):
        self.calls.append(
            {
                "session": session,
                "query": query,
                "top_k": top_k,
                "user_id": user_id,
            }
        )
        return [SimpleNamespace(chunk_id=chunk_id) for chunk_id in self.result_sets.pop(0)]


@pytest.mark.asyncio
async def test_evaluator_calculates_metrics_and_forwards_user_scope():
    user_id = uuid4()
    relevant_first = uuid4()
    relevant_second = uuid4()
    irrelevant = uuid4()
    cases = [
        RetrievalEvaluationCase(
            query="first query",
            relevant_ids={relevant_first},
            relevance={relevant_first: 3},
        ),
        RetrievalEvaluationCase(
            query="second query",
            relevant_ids={relevant_second},
            relevance={relevant_second: 3},
        ),
    ]
    retriever = FakeRetriever([[relevant_first, irrelevant], [irrelevant, relevant_second]])

    result = await RetrievalEvaluator(retriever).evaluate(object(), cases, user_id=user_id, k=2)

    assert result.recall_at_k == pytest.approx(1.0)
    assert result.mrr == pytest.approx(0.75)
    assert 0.0 <= result.ndcg_at_k <= 1.0
    assert len(retriever.calls) == 2
    assert all(call["user_id"] == user_id for call in retriever.calls)
    assert all(call["top_k"] == 2 for call in retriever.calls)
    assert [call["query"] for call in retriever.calls] == [case.query for case in cases]


@pytest.mark.asyncio
async def test_evaluator_rejects_empty_cases_before_retrieval():
    retriever = FakeRetriever([])

    with pytest.raises(ValueError, match="At least one evaluation case"):
        await RetrievalEvaluator(retriever).evaluate(object(), [], user_id=uuid4())

    assert retriever.calls == []


@pytest.mark.parametrize("k", [0, -1, 101])
@pytest.mark.asyncio
async def test_evaluator_rejects_invalid_k_before_retrieval(k):
    retriever = FakeRetriever([])
    case = RetrievalEvaluationCase(
        query="test query",
        relevant_ids=set(),
        relevance={},
    )

    with pytest.raises(ValueError, match="between 1 and 100"):
        await RetrievalEvaluator(retriever).evaluate(object(), [case], user_id=uuid4(), k=k)

    assert retriever.calls == []
