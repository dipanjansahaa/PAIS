"""Tests for task domain models."""

from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.tasks.models import Task, TaskSource, TaskStatus


def test_task_stores_domain_fields() -> None:
    """A task should preserve identity, lifecycle, scheduling, and provenance."""

    task_id = uuid4()
    user_id = uuid4()
    project_id = uuid4()
    commitment_id = uuid4()
    chunk_id = uuid4()
    due_at = datetime(2026, 10, 5, 12, 0)

    task = Task(
        id=task_id,
        user_id=user_id,
        project_id=project_id,
        commitment_id=commitment_id,
        description="Review the deployment",
        owner="Dipanjan",
        due_at=due_at,
        priority="high",
        status=TaskStatus.IN_PROGRESS,
        sources=[TaskSource(chunk_id=chunk_id)],
    )

    assert task.id == task_id
    assert task.user_id == user_id
    assert task.project_id == project_id
    assert task.commitment_id == commitment_id
    assert task.description == "Review the deployment"
    assert task.owner == "Dipanjan"
    assert task.due_at == due_at
    assert task.priority == "high"
    assert task.status is TaskStatus.IN_PROGRESS
    assert task.sources[0].chunk_id == chunk_id


def test_task_defaults_to_open() -> None:
    """New tasks should begin in the open state."""

    task = Task(
        id=uuid4(),
        user_id=uuid4(),
        description="Review the deployment",
        sources=[TaskSource(chunk_id=uuid4())],
    )

    assert task.status is TaskStatus.OPEN


def test_task_requires_provenance() -> None:
    """A task must retain at least one source reference."""

    with pytest.raises(ValidationError):
        Task(
            id=uuid4(),
            user_id=uuid4(),
            description="Review the deployment",
            sources=[],
        )


def test_task_requires_description() -> None:
    """A task description cannot be empty."""

    with pytest.raises(ValidationError):
        Task(
            id=uuid4(),
            user_id=uuid4(),
            description="",
            sources=[TaskSource(chunk_id=uuid4())],
        )
