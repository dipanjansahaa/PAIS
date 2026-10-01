"""Tests for DailySnapshot integration with the priority engine."""

from datetime import datetime
from uuid import uuid4

from app.daily.models import (
    DailyCommitment,
    DailySnapshot,
    DailyTask,
)
from app.daily.priority import (
    PriorityEngine,
    PriorityItemType,
    PriorityReasonCode,
)


def _snapshot(
    *,
    tasks: tuple[DailyTask, ...] = (),
    commitments: tuple[DailyCommitment, ...] = (),
) -> DailySnapshot:
    return DailySnapshot(
        day=datetime(2026, 10, 2).date(),
        timezone_name="UTC",
        window_start_utc=datetime(2026, 10, 2, 0, 0),
        window_end_utc=datetime(2026, 10, 3, 0, 0),
        open_tasks=tasks,
        open_commitments=commitments,
        recent_decisions=(),
        recent_changes=(),
    )


def test_prioritize_snapshot_uses_tasks_from_snapshot():
    task = DailyTask(
        id=uuid4(),
        description="Deploy service",
        owner=None,
        due_at=datetime(2026, 10, 2, 9, 0),
        priority="high",
        status="open",
        project_id=None,
        commitment_id=None,
    )

    snapshot = _snapshot(tasks=(task,))

    result = PriorityEngine().prioritize_snapshot(snapshot)

    assert len(result) == 1
    assert result[0].item_type == PriorityItemType.TASK
    assert result[0].item_id == task.id
    assert result[0].title == "Deploy service"
    assert result[0].score == 65


def test_prioritize_snapshot_uses_commitments_from_snapshot():
    commitment = DailyCommitment(
        id=uuid4(),
        description="Send client response",
        owner=None,
        deadline_at=datetime(2026, 10, 2, 9, 0),
        status="open",
        project_id=None,
    )

    snapshot = _snapshot(commitments=(commitment,))

    result = PriorityEngine().prioritize_snapshot(snapshot)

    assert len(result) == 1
    assert result[0].item_type == PriorityItemType.COMMITMENT
    assert result[0].item_id == commitment.id
    assert result[0].title == "Send client response"
    assert result[0].score == 30


def test_prioritize_snapshot_combines_tasks_and_commitments():
    task = DailyTask(
        id=uuid4(),
        description="Deploy service",
        owner=None,
        due_at=datetime(2026, 10, 2, 9, 0),
        priority="high",
        status="open",
        project_id=None,
        commitment_id=None,
    )

    commitment = DailyCommitment(
        id=uuid4(),
        description="Send client response",
        owner=None,
        deadline_at=datetime(2026, 10, 9, 0),
        status="open",
        project_id=None,
    )

    snapshot = _snapshot(
        tasks=(task,),
        commitments=(commitment,),
    )

    result = PriorityEngine().prioritize_snapshot(snapshot)

    assert len(result) == 2
    assert result[0].item_id == task.id
    assert result[1].item_id == commitment.id


def test_prioritize_snapshot_preserves_explainable_reasons():
    task = DailyTask(
        id=uuid4(),
        description="Prepare deliverable",
        owner=None,
        due_at=datetime(2026, 10, 2, 9, 0),
        priority="high",
        status="open",
        project_id=None,
        commitment_id=uuid4(),
    )

    snapshot = _snapshot(tasks=(task,))

    result = PriorityEngine().prioritize_snapshot(snapshot)

    reason_codes = {
        reason.code
        for reason in result[0].reasons
    }

    assert PriorityReasonCode.EXPLICIT_PRIORITY in reason_codes
    assert PriorityReasonCode.DUE_SOON in reason_codes
    assert PriorityReasonCode.LINKED_COMMITMENT in reason_codes


def test_prioritize_snapshot_does_not_include_recent_decisions_as_actions():
    from app.daily.models import DailyDecision

    decision = DailyDecision(
        id=uuid4(),
        title="Database decision",
        description="Use PostgreSQL",
        decision_date=datetime(2026, 10, 2, 8, 0),
        status="active",
        project_id=None,
    )

    snapshot = DailySnapshot(
        day=datetime(2026, 10, 2).date(),
        timezone_name="UTC",
        window_start_utc=datetime(2026, 10, 2, 0, 0),
        window_end_utc=datetime(2026, 10, 3, 0, 0),
        open_tasks=(),
        open_commitments=(),
        recent_decisions=(decision,),
        recent_changes=(),
    )

    result = PriorityEngine().prioritize_snapshot(snapshot)

    assert result == ()


def test_prioritize_snapshot_empty_snapshot_returns_empty_result():
    snapshot = _snapshot()

    result = PriorityEngine().prioritize_snapshot(snapshot)

    assert result == ()