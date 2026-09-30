import uuid
from datetime import datetime, timezone

from app.database.models.commitment import Commitment, CommitmentSource
from app.database.models.task import Task, TaskSource


def test_task_table_definition():
    table = Task.__table__

    assert table.name == "tasks"

    assert "id" in table.c
    assert "user_id" in table.c
    assert "project_id" in table.c
    assert "commitment_id" in table.c
    assert "description" in table.c
    assert "owner" in table.c
    assert "due_at" in table.c
    assert "priority" in table.c
    assert "status" in table.c


def test_commitment_table_definition():
    table = Commitment.__table__

    assert table.name == "commitments"

    assert "id" in table.c
    assert "user_id" in table.c
    assert "project_id" in table.c
    assert "description" in table.c
    assert "owner" in table.c
    assert "deadline_at" in table.c
    assert "status" in table.c


def test_task_source_table_definition():
    table = TaskSource.__table__

    assert table.name == "task_sources"

    assert table.primary_key.columns.keys() == ["task_id", "chunk_id"]


def test_commitment_source_table_definition():
    table = CommitmentSource.__table__

    assert table.name == "commitment_sources"

    assert table.primary_key.columns.keys() == [
        "commitment_id",
        "chunk_id",
    ]


def test_task_relationships():
    assert Task.user.property.back_populates == "tasks"
    assert Task.project.property.back_populates == "tasks"
    assert Task.commitment.property.back_populates == "tasks"
    assert Task.sources.property.back_populates == "task"


def test_commitment_relationships():
    assert Commitment.user.property.back_populates == "commitments"
    assert Commitment.project.property.back_populates == "commitments"
    assert Commitment.tasks.property.back_populates == "commitment"
    assert Commitment.sources.property.back_populates == "commitment"


def test_task_status_default():
    column = Task.__table__.c.status

    assert column.default is not None
    assert column.default.arg == "open"
    assert column.server_default is not None


def test_commitment_status_default():
    column = Commitment.__table__.c.status

    assert column.default is not None
    assert column.default.arg == "open"
    assert column.server_default is not None


def test_task_supports_commitment():
    commitment_id = uuid.uuid4()

    task = Task(
        user_id=uuid.uuid4(),
        description="Review deployment logs",
        commitment_id=commitment_id,
    )

    assert task.commitment_id == commitment_id


def test_task_supports_deadline_and_priority():
    due_at = datetime(
        2026,
        10,
        1,
        12,
        0,
        tzinfo=timezone.utc,
    )

    task = Task(
        user_id=uuid.uuid4(),
        description="Deploy service",
        due_at=due_at,
        priority="high",
    )

    assert task.due_at == due_at
    assert task.priority == "high"