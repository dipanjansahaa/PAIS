"""Tests for commitment domain models."""

from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.commitments.models import Commitment, CommitmentSource, CommitmentStatus


def test_commitment_stores_domain_fields() -> None:
    """A commitment should preserve lifecycle, scheduling, ownership, and provenance."""

    commitment_id = uuid4()
    user_id = uuid4()
    project_id = uuid4()
    chunk_id = uuid4()
    deadline_at = datetime(2026, 10, 5, 12, 0)

    commitment = Commitment(
        id=commitment_id,
        user_id=user_id,
        project_id=project_id,
        description="Review the deployment",
        owner="Dipanjan",
        deadline_at=deadline_at,
        status=CommitmentStatus.FULFILLED,
        sources=[CommitmentSource(chunk_id=chunk_id)],
    )

    assert commitment.id == commitment_id
    assert commitment.user_id == user_id
    assert commitment.project_id == project_id
    assert commitment.description == "Review the deployment"
    assert commitment.owner == "Dipanjan"
    assert commitment.deadline_at == deadline_at
    assert commitment.status is CommitmentStatus.FULFILLED
    assert commitment.sources[0].chunk_id == chunk_id


def test_commitment_defaults_to_open() -> None:
    """New commitments should begin in the open state."""

    commitment = Commitment(
        id=uuid4(),
        user_id=uuid4(),
        description="Review the deployment",
        sources=[CommitmentSource(chunk_id=uuid4())],
    )

    assert commitment.status is CommitmentStatus.OPEN


def test_commitment_requires_provenance() -> None:
    """A commitment must retain at least one source reference."""

    with pytest.raises(ValidationError):
        Commitment(
            id=uuid4(),
            user_id=uuid4(),
            description="Review the deployment",
            sources=[],
        )


def test_commitment_requires_description() -> None:
    """A commitment description cannot be empty."""

    with pytest.raises(ValidationError):
        Commitment(
            id=uuid4(),
            user_id=uuid4(),
            description="",
            sources=[CommitmentSource(chunk_id=uuid4())],
        )
