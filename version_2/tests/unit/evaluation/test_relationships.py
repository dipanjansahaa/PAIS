"""Unit tests for relationship-context evaluation."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.evaluation.cases import RelationshipEvaluationCase
from app.evaluation.relationships import RelationshipContextEvaluator


class FakeRelationshipContextBuilder:
    def __init__(self, result_sets):
        self.result_sets = list(result_sets)
        self.calls = []

    async def build(
        self,
        session,
        *,
        user_id,
        entity_type,
        entity_id,
        limit=20,
        as_of=None,
    ):
        self.calls.append(
            {
                "session": session,
                "user_id": user_id,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "limit": limit,
                "as_of": as_of,
            }
        )
        relationships = [
            SimpleNamespace(relationship_id=str(item_id)) for item_id in self.result_sets.pop(0)
        ]
        return SimpleNamespace(relationships=relationships)


@pytest.mark.asyncio
async def test_evaluator_calculates_relationship_metrics_and_forwards_scope():
    user_id = uuid4()
    entity_id = uuid4()
    relevant_first = uuid4()
    relevant_second = uuid4()
    irrelevant = uuid4()
    as_of = datetime(2026, 10, 31, tzinfo=UTC)
    cases = [
        RelationshipEvaluationCase(
            entity_type="project",
            entity_id=entity_id,
            relevant_ids={relevant_first},
            relevance={relevant_first: 3},
        ),
        RelationshipEvaluationCase(
            entity_type="project",
            entity_id=entity_id,
            relevant_ids={relevant_second},
            relevance={relevant_second: 3},
        ),
    ]
    builder = FakeRelationshipContextBuilder(
        [[relevant_first, irrelevant], [irrelevant, relevant_second]]
    )

    result = await RelationshipContextEvaluator(builder).evaluate(
        object(),
        cases,
        user_id=user_id,
        k=2,
        as_of=as_of,
    )

    assert result.recall_at_k == pytest.approx(1.0)
    assert result.mrr == pytest.approx(0.75)
    assert 0.0 <= result.ndcg_at_k <= 1.0
    assert len(builder.calls) == 2
    assert all(call["user_id"] == user_id for call in builder.calls)
    assert all(call["as_of"] == as_of for call in builder.calls)
    assert all(call["limit"] == 2 for call in builder.calls)


@pytest.mark.asyncio
async def test_evaluator_rejects_empty_cases():
    evaluator = RelationshipContextEvaluator(FakeRelationshipContextBuilder([]))

    with pytest.raises(ValueError, match="At least one evaluation case"):
        await evaluator.evaluate(
            object(),
            [],
            user_id=uuid4(),
            as_of=datetime(2026, 10, 31, tzinfo=UTC),
        )


@pytest.mark.parametrize("k", [0, -1, 101])
@pytest.mark.asyncio
async def test_evaluator_rejects_invalid_k(k):
    evaluator = RelationshipContextEvaluator(FakeRelationshipContextBuilder([]))
    case = RelationshipEvaluationCase(
        entity_type="project",
        entity_id=uuid4(),
        relevant_ids=set(),
        relevance={},
    )

    with pytest.raises(ValueError, match="between 1 and 100"):
        await evaluator.evaluate(
            object(),
            [case],
            user_id=uuid4(),
            k=k,
            as_of=datetime(2026, 10, 31, tzinfo=UTC),
        )


@pytest.mark.parametrize(
    "as_of",
    [
        datetime(2026, 10, 31),
        None,
    ],
)
@pytest.mark.asyncio
async def test_evaluator_rejects_naive_or_missing_as_of(as_of):
    evaluator = RelationshipContextEvaluator(FakeRelationshipContextBuilder([]))
    case = RelationshipEvaluationCase(
        entity_type="project",
        entity_id=uuid4(),
        relevant_ids=set(),
        relevance={},
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        await evaluator.evaluate(
            object(),
            [case],
            user_id=uuid4(),
            as_of=as_of,
        )
