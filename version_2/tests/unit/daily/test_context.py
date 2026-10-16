"""Tests for the daily intelligence context builder."""

from datetime import datetime
from uuid import uuid4

from app.daily.context import (
    DailyContextBuilder,
    DailyIntelligenceContext,
)
from app.daily.models import (
    DailyChange,
    DailyDecision,
    DailySnapshot,
    DailyTask,
)
from app.daily.priority import (
    PrioritizedItem,
    PriorityItemType,
    PriorityReason,
    PriorityReasonCode,
)


def _snapshot(
    *,
    decisions: tuple[DailyDecision, ...] = (),
    changes: tuple[DailyChange, ...] = (),
) -> DailySnapshot:
    return DailySnapshot(
        day=datetime(2026, 10, 2).date(),
        timezone_name="Asia/Kolkata",
        window_start_utc=datetime(2026, 10, 1, 18, 30),
        window_end_utc=datetime(2026, 10, 2, 18, 30),
        open_tasks=(),
        open_commitments=(),
        recent_decisions=decisions,
        recent_changes=changes,
    )


def _prioritized_task(
    *,
    title: str = "Deploy service",
) -> PrioritizedItem:
    return PrioritizedItem(
        item_type=PriorityItemType.TASK,
        item_id=uuid4(),
        title=title,
        score=65,
        reasons=(
            PriorityReason(
                code=PriorityReasonCode.EXPLICIT_PRIORITY,
                points=35,
                message="Explicit priority: high.",
            ),
        ),
    )


def test_build_returns_daily_intelligence_context():
    snapshot = _snapshot()
    prioritized_items = (_prioritized_task(),)

    result = DailyContextBuilder().build(
        snapshot,
        prioritized_items,
    )

    assert isinstance(result, DailyIntelligenceContext)


def test_build_preserves_snapshot_metadata():
    snapshot = _snapshot()

    result = DailyContextBuilder().build(
        snapshot,
        (),
    )

    assert result.day == snapshot.day
    assert result.timezone_name == snapshot.timezone_name
    assert result.window_start_utc == snapshot.window_start_utc
    assert result.window_end_utc == snapshot.window_end_utc


def test_build_includes_prioritized_items():
    snapshot = _snapshot()
    prioritized_items = (
        _prioritized_task(title="Deploy service"),
        _prioritized_task(title="Prepare report"),
    )

    result = DailyContextBuilder().build(
        snapshot,
        prioritized_items,
    )

    assert result.prioritized_items == prioritized_items


def test_build_includes_recent_decisions():
    decision = DailyDecision(
        id=uuid4(),
        title="Database choice",
        description="Use PostgreSQL",
        decision_date=datetime(2026, 10, 2, 9, 0),
        status="active",
        project_id=None,
    )

    snapshot = _snapshot(
        decisions=(decision,),
    )

    result = DailyContextBuilder().build(
        snapshot,
        (),
    )

    assert result.recent_decisions == (decision,)


def test_build_includes_recent_changes():
    change = DailyChange(
        entity_type="task",
        entity_id=uuid4(),
        changed_at=datetime(2026, 10, 2, 10, 0),
    )

    snapshot = _snapshot(
        changes=(change,),
    )

    result = DailyContextBuilder().build(
        snapshot,
        (),
    )

    assert result.recent_changes == (change,)


def test_build_preserves_order_of_prioritized_items():
    first = _prioritized_task(title="First action")
    second = _prioritized_task(title="Second action")

    snapshot = _snapshot()

    result = DailyContextBuilder().build(
        snapshot,
        (first, second),
    )

    assert result.prioritized_items == (first, second)


def test_build_empty_snapshot_returns_empty_context_collections():
    snapshot = _snapshot()

    result = DailyContextBuilder().build(
        snapshot,
        (),
    )

    assert result.prioritized_items == ()
    assert result.recent_decisions == ()
    assert result.recent_changes == ()