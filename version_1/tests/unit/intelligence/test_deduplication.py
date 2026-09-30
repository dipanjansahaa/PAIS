"""Tests for deterministic intelligence deduplication."""

from datetime import datetime
from uuid import uuid4

from app.intelligence.deduplication import (
    deduplicate_commitments,
    deduplicate_decisions,
    deduplicate_intelligence,
    deduplicate_tasks,
    normalize_text,
)
from app.intelligence.models import (
    CommitmentCandidate,
    DecisionCandidate,
    IntelligenceSource,
    StructuredIntelligence,
    TaskCandidate,
)


def source(chunk_id=None):
    """Create an intelligence source."""

    return IntelligenceSource(
        chunk_id=chunk_id or uuid4(),
    )


def test_normalize_text_is_deterministic():
    """Normalization should collapse equivalent textual forms."""

    assert normalize_text(
        "  Review   THE API  "
    ) == "review the api"


def test_normalize_text_preserves_meaningful_words():
    """Normalization should not remove meaningful words."""

    assert normalize_text(
        "Review the API"
    ) != normalize_text(
        "Do not review the API"
    )


def test_task_deduplication_merges_normalized_duplicates():
    """Equivalent task identities should merge."""

    first_source = source()
    second_source = source()

    tasks = [
        TaskCandidate(
            description=" Review   the API ",
            owner="Dipanjan",
            sources=[first_source],
        ),
        TaskCandidate(
            description="review the api",
            owner="dipanjan",
            sources=[second_source],
        ),
    ]

    result = deduplicate_tasks(tasks)

    assert len(result) == 1
    assert result[0].description == " Review   the API "
    assert result[0].sources == [
        first_source,
        second_source,
    ]


def test_task_deduplication_does_not_merge_different_owners():
    """Different explicit owners represent different candidates."""

    tasks = [
        TaskCandidate(
            description="Review the API",
            owner="Alice",
            sources=[source()],
        ),
        TaskCandidate(
            description="Review the API",
            owner="Bob",
            sources=[source()],
        ),
    ]

    result = deduplicate_tasks(tasks)

    assert len(result) == 2


def test_task_deduplication_does_not_merge_missing_owner_with_named_owner():
    """Unknown ownership must not be treated as a wildcard."""

    tasks = [
        TaskCandidate(
            description="Review the API",
            owner=None,
            sources=[source()],
        ),
        TaskCandidate(
            description="Review the API",
            owner="Dipanjan",
            sources=[source()],
        ),
    ]

    result = deduplicate_tasks(tasks)

    assert len(result) == 2


def test_task_deduplication_fills_missing_due_date():
    """A missing field may be filled by a duplicate candidate."""

    chunk_a = source()
    chunk_b = source()

    due_at = datetime(2026, 10, 5, 12, 0)

    tasks = [
        TaskCandidate(
            description="Review API",
            owner="Dipanjan",
            due_at=None,
            priority="high",
            sources=[chunk_a],
        ),
        TaskCandidate(
            description="review api",
            owner="dipanjan",
            due_at=due_at,
            priority="high",
            sources=[chunk_b],
        ),
    ]

    result = deduplicate_tasks(tasks)

    assert len(result) == 1
    assert result[0].due_at == due_at
    assert result[0].priority == "high"
    assert result[0].sources == [chunk_a, chunk_b]


def test_task_deduplication_preserves_conflicting_due_dates():
    """Conflicting due dates must not be silently merged."""

    tasks = [
        TaskCandidate(
            description="Review API",
            owner="Dipanjan",
            due_at=datetime(2026, 10, 5),
            sources=[source()],
        ),
        TaskCandidate(
            description="review api",
            owner="dipanjan",
            due_at=datetime(2026, 10, 7),
            sources=[source()],
        ),
    ]

    result = deduplicate_tasks(tasks)

    assert len(result) == 2


def test_commitment_deduplication_merges_duplicates():
    """Equivalent commitments should merge."""

    first_source = source()
    second_source = source()

    commitments = [
        CommitmentCandidate(
            description="Finish the migration",
            owner="Dipanjan",
            sources=[first_source],
        ),
        CommitmentCandidate(
            description=" finish   THE migration ",
            owner="dipanjan",
            sources=[second_source],
        ),
    ]

    result = deduplicate_commitments(commitments)

    assert len(result) == 1
    assert result[0].sources == [
        first_source,
        second_source,
    ]


def test_commitment_deduplication_preserves_conflicting_deadlines():
    """Conflicting deadlines must remain separate."""

    commitments = [
        CommitmentCandidate(
            description="Finish migration",
            owner="Dipanjan",
            deadline_at=datetime(2026, 10, 5),
            sources=[source()],
        ),
        CommitmentCandidate(
            description="finish migration",
            owner="dipanjan",
            deadline_at=datetime(2026, 10, 8),
            sources=[source()],
        ),
    ]

    result = deduplicate_commitments(commitments)

    assert len(result) == 2


def test_decision_deduplication_merges_exact_normalized_decisions():
    """Equivalent decisions should merge."""

    first_source = source()
    second_source = source()

    decisions = [
        DecisionCandidate(
            title="Database Choice",
            description="Use PostgreSQL",
            sources=[first_source],
        ),
        DecisionCandidate(
            title=" database   choice ",
            description="use postgresql",
            sources=[second_source],
        ),
    ]

    result = deduplicate_decisions(decisions)

    assert len(result) == 1
    assert result[0].sources == [
        first_source,
        second_source,
    ]


def test_decision_deduplication_keeps_different_decisions():
    """Different decision descriptions must remain separate."""

    decisions = [
        DecisionCandidate(
            title="Database",
            description="Use PostgreSQL",
            sources=[source()],
        ),
        DecisionCandidate(
            title="Database",
            description="Use MySQL",
            sources=[source()],
        ),
    ]

    result = deduplicate_decisions(decisions)

    assert len(result) == 2


def test_decision_deduplication_preserves_conflicting_dates():
    """Conflicting decision dates must not be silently merged."""

    decisions = [
        DecisionCandidate(
            title="Database",
            description="Use PostgreSQL",
            decision_date=datetime(2026, 10, 5),
            sources=[source()],
        ),
        DecisionCandidate(
            title="database",
            description="use postgresql",
            decision_date=datetime(2026, 10, 7),
            sources=[source()],
        ),
    ]

    result = deduplicate_decisions(decisions)

    assert len(result) == 2


def test_deduplicate_intelligence_only_changes_supported_categories():
    """The aggregate function should preserve all other categories."""

    intelligence = StructuredIntelligence(
        tasks=[
            TaskCandidate(
                description="Review API",
                sources=[source()],
            ),
            TaskCandidate(
                description="review api",
                sources=[source()],
            ),
        ],
        commitments=[
            CommitmentCandidate(
                description="Finish migration",
                sources=[source()],
            ),
        ],
    )

    result = deduplicate_intelligence(intelligence)

    assert len(result.tasks) == 1
    assert len(result.commitments) == 1
    assert result.decisions == []
    assert result.projects == []
    assert result.people == []
    assert result.risks == []
    assert result.follow_ups == []
    assert result.deadlines == []