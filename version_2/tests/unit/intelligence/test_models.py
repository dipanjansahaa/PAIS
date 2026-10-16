"""Tests for structured intelligence models."""

from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.intelligence.models import (
    CommitmentCandidate,
    DecisionCandidate,
    IntelligenceSource,
    StructuredIntelligence,
    TaskCandidate,
)


def test_task_candidate_requires_source():
    """A task candidate must retain provenance."""

    with pytest.raises(ValidationError):
        TaskCandidate(
            description="Review the API",
            sources=[],
        )


def test_task_candidate_stores_structured_fields():
    """Task candidate should preserve extracted fields."""

    chunk_id = uuid4()
    due_at = datetime(2026, 10, 5, 12, 0)

    task = TaskCandidate(
        description="Review the API",
        owner="Dipanjan",
        due_at=due_at,
        priority="high",
        sources=[
            IntelligenceSource(chunk_id=chunk_id),
        ],
    )

    assert task.description == "Review the API"
    assert task.owner == "Dipanjan"
    assert task.due_at == due_at
    assert task.priority == "high"
    assert task.sources[0].chunk_id == chunk_id


def test_commitment_candidate_requires_source():
    """A commitment must retain provenance."""

    with pytest.raises(ValidationError):
        CommitmentCandidate(
            description="Review the deployment",
            sources=[],
        )


def test_decision_candidate_stores_fields():
    """Decision candidate should preserve decision information."""

    chunk_id = uuid4()

    decision = DecisionCandidate(
        title="Database choice",
        description="Use PostgreSQL for PAIS.",
        sources=[
            IntelligenceSource(chunk_id=chunk_id),
        ],
    )

    assert decision.title == "Database choice"
    assert decision.description == "Use PostgreSQL for PAIS."
    assert decision.sources[0].chunk_id == chunk_id


def test_structured_intelligence_allows_empty_categories():
    """Extraction may legitimately produce no items."""

    intelligence = StructuredIntelligence()

    assert intelligence.tasks == []
    assert intelligence.commitments == []
    assert intelligence.decisions == []
    assert intelligence.projects == []
    assert intelligence.people == []
    assert intelligence.risks == []
    assert intelligence.follow_ups == []
    assert intelligence.deadlines == []


def test_structured_intelligence_groups_candidates():
    """Structured intelligence should preserve extracted categories."""

    chunk_id = uuid4()

    intelligence = StructuredIntelligence(
        tasks=[
            TaskCandidate(
                description="Review API",
                sources=[
                    IntelligenceSource(
                        chunk_id=chunk_id,
                    ),
                ],
            ),
        ],
        commitments=[
            CommitmentCandidate(
                description="Finish API review",
                sources=[
                    IntelligenceSource(
                        chunk_id=chunk_id,
                    ),
                ],
            ),
        ],
    )

    assert len(intelligence.tasks) == 1
    assert len(intelligence.commitments) == 1
    assert intelligence.tasks[0].sources[0].chunk_id == chunk_id
    assert (
        intelligence.commitments[0].sources[0].chunk_id
        == chunk_id
    )