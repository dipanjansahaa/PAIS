"""Tests for the deterministic daily priority engine."""

from datetime import datetime, timedelta
from uuid import uuid4

from app.daily.models import DailyCommitment, DailyTask
from app.daily.priority import (
    PriorityEngine,
    PriorityItemType,
    PriorityReasonCode,
)


def _window() -> tuple[datetime, datetime]:
    start = datetime(2026, 10, 2, 0, 0)
    end = datetime(2026, 10, 3, 0, 0)

    return start, end


def test_high_priority_task_scores_above_medium_priority_task():
    start, end = _window()

    high_task = DailyTask(
        id=uuid4(),
        description="Deploy service",
        owner=None,
        due_at=datetime(2026, 10, 2, 10, 0),
        priority="high",
        status="open",
        project_id=None,
        commitment_id=None,
    )

    medium_task = DailyTask(
        id=uuid4(),
        description="Review documentation",
        owner=None,
        due_at=datetime(2026, 10, 2, 10, 0),
        priority="medium",
        status="open",
        project_id=None,
        commitment_id=None,
    )

    result = PriorityEngine().prioritize(
        tasks=(medium_task, high_task),
        commitments=(),
        window_start_utc=start,
        window_end_utc=end,
    )

    assert result[0].item_id == high_task.id
    assert result[1].item_id == medium_task.id


def test_urgent_priority_scores_above_high_priority():
    start, end = _window()

    urgent_task = DailyTask(
        id=uuid4(),
        description="Resolve production issue",
        owner=None,
        due_at=datetime(2026, 10, 2, 10, 0),
        priority="urgent",
        status="open",
        project_id=None,
        commitment_id=None,
    )

    high_task = DailyTask(
        id=uuid4(),
        description="Review deployment",
        owner=None,
        due_at=datetime(2026, 10, 2, 10, 0),
        priority="high",
        status="open",
        project_id=None,
        commitment_id=None,
    )

    result = PriorityEngine().prioritize(
        tasks=(high_task, urgent_task),
        commitments=(),
        window_start_utc=start,
        window_end_utc=end,
    )

    assert result[0].item_id == urgent_task.id


def test_early_due_task_scores_above_later_due_task():
    start, end = _window()

    early_task = DailyTask(
        id=uuid4(),
        description="Morning task",
        owner=None,
        due_at=datetime(2026, 10, 2, 9, 0),
        priority=None,
        status="open",
        project_id=None,
        commitment_id=None,
    )

    late_task = DailyTask(
        id=uuid4(),
        description="Afternoon task",
        owner=None,
        due_at=datetime(2026, 10, 2, 18, 0),
        priority=None,
        status="open",
        project_id=None,
        commitment_id=None,
    )

    result = PriorityEngine().prioritize(
        tasks=(late_task, early_task),
        commitments=(),
        window_start_utc=start,
        window_end_utc=end,
    )

    assert result[0].item_id == early_task.id


def test_task_linked_to_commitment_gets_additional_priority():
    start, end = _window()

    linked_task = DailyTask(
        id=uuid4(),
        description="Prepare commitment deliverable",
        owner=None,
        due_at=datetime(2026, 10, 2, 18, 0),
        priority=None,
        status="open",
        project_id=None,
        commitment_id=uuid4(),
    )

    unlinked_task = DailyTask(
        id=uuid4(),
        description="Routine task",
        owner=None,
        due_at=datetime(2026, 10, 2, 18, 0),
        priority=None,
        status="open",
        project_id=None,
        commitment_id=None,
    )

    result = PriorityEngine().prioritize(
        tasks=(unlinked_task, linked_task),
        commitments=(),
        window_start_utc=start,
        window_end_utc=end,
    )

    assert result[0].item_id == linked_task.id
    assert result[0].score == 25
    assert any(
        reason.code == PriorityReasonCode.LINKED_COMMITMENT
        for reason in result[0].reasons
    )


def test_commitment_uses_deadline_urgency():
    start, end = _window()

    commitment = DailyCommitment(
        id=uuid4(),
        description="Send client response",
        owner=None,
        deadline_at=datetime(2026, 10, 2, 9, 0),
        status="open",
        project_id=None,
    )

    result = PriorityEngine().prioritize(
        tasks=(),
        commitments=(commitment,),
        window_start_utc=start,
        window_end_utc=end,
    )

    assert len(result) == 1
    assert result[0].item_type == PriorityItemType.COMMITMENT
    assert result[0].score == 30
    assert result[0].reasons[0].code == PriorityReasonCode.DUE_SOON


def test_missing_due_date_does_not_add_urgency():
    start, end = _window()

    task = DailyTask(
        id=uuid4(),
        description="Undated task",
        owner=None,
        due_at=None,
        priority=None,
        status="open",
        project_id=None,
        commitment_id=None,
    )

    result = PriorityEngine().prioritize(
        tasks=(task,),
        commitments=(),
        window_start_utc=start,
        window_end_utc=end,
    )

    assert result[0].score == 0
    assert result[0].reasons[0].code == PriorityReasonCode.NO_DUE_DATE


def test_priority_is_case_and_whitespace_insensitive():
    start, end = _window()

    task = DailyTask(
        id=uuid4(),
        description="Important task",
        owner=None,
        due_at=datetime(2026, 10, 2, 18, 0),
        priority="  HIGH ",
        status="open",
        project_id=None,
        commitment_id=None,
    )

    result = PriorityEngine().prioritize(
        tasks=(task,),
        commitments=(),
        window_start_utc=start,
        window_end_utc=end,
    )

    assert result[0].score == 45


def test_priority_ordering_is_deterministic_for_equal_scores():
    start, end = _window()

    first = DailyTask(
        id=uuid4(),
        description="Alpha task",
        owner=None,
        due_at=datetime(2026, 10, 2, 18, 0),
        priority=None,
        status="open",
        project_id=None,
        commitment_id=None,
    )

    second = DailyTask(
        id=uuid4(),
        description="Beta task",
        owner=None,
        due_at=datetime(2026, 10, 2, 18, 0),
        priority=None,
        status="open",
        project_id=None,
        commitment_id=None,
    )

    result_one = PriorityEngine().prioritize(
        tasks=(second, first),
        commitments=(),
        window_start_utc=start,
        window_end_utc=end,
    )

    result_two = PriorityEngine().prioritize(
        tasks=(first, second),
        commitments=(),
        window_start_utc=start,
        window_end_utc=end,
    )

    assert [item.item_id for item in result_one] == [
        item.item_id for item in result_two
    ]