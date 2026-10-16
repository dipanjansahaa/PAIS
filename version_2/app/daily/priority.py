"""Deterministic priority engine for daily intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.daily.models import (
    DailyCommitment,
    DailySnapshot,
    DailyTask,
)


class PriorityItemType(StrEnum):
    """Supported daily priority item types."""

    TASK = "task"
    COMMITMENT = "commitment"


class PriorityReasonCode(StrEnum):
    """Reasons contributing to a deterministic priority score."""

    EXPLICIT_PRIORITY = "explicit_priority"
    DUE_SOON = "due_soon"
    DUE_LATER = "due_later"
    LINKED_COMMITMENT = "linked_commitment"
    NO_DUE_DATE = "no_due_date"


@dataclass(frozen=True, slots=True)
class PriorityReason:
    """Explain one factor contributing to a priority score."""

    code: PriorityReasonCode
    points: int
    message: str


@dataclass(frozen=True, slots=True)
class PrioritizedItem:
    """A daily item with a deterministic priority score."""

    item_type: PriorityItemType
    item_id: UUID
    title: str
    score: int
    reasons: tuple[PriorityReason, ...]


class PriorityEngine:
    """Rank daily tasks and commitments deterministically."""

    _EXPLICIT_PRIORITY_POINTS = {
        "urgent": 50,
        "high": 35,
        "medium": 20,
        "low": 5,
    }

    _DUE_SOON_POINTS = 30
    _DUE_LATER_POINTS = 10
    _LINKED_COMMITMENT_POINTS = 15
    _NO_DUE_DATE_POINTS = 0

    def prioritize_snapshot(
        self,
        snapshot: DailySnapshot,
    ) -> tuple[PrioritizedItem, ...]:
        """Prioritize the actionable items contained in a daily snapshot."""

        return self.prioritize(
            tasks=snapshot.open_tasks,
            commitments=snapshot.open_commitments,
            window_start_utc=snapshot.window_start_utc,
            window_end_utc=snapshot.window_end_utc,
        )

    def prioritize(
        self,
        *,
        tasks: tuple[DailyTask, ...],
        commitments: tuple[DailyCommitment, ...],
        window_start_utc: datetime,
        window_end_utc: datetime,
    ) -> tuple[PrioritizedItem, ...]:
        """Return daily tasks and commitments ordered by deterministic priority."""

        items: list[PrioritizedItem] = []

        for task in tasks:
            items.append(
                self._prioritize_task(
                    task,
                    window_start_utc=window_start_utc,
                    window_end_utc=window_end_utc,
                )
            )

        for commitment in commitments:
            items.append(
                self._prioritize_commitment(
                    commitment,
                    window_start_utc=window_start_utc,
                    window_end_utc=window_end_utc,
                )
            )

        return tuple(
            sorted(
                items,
                key=lambda item: (
                    -item.score,
                    item.title.casefold(),
                    str(item.item_id),
                ),
            )
        )

    def _prioritize_task(
        self,
        task: DailyTask,
        *,
        window_start_utc: datetime,
        window_end_utc: datetime,
    ) -> PrioritizedItem:
        reasons: list[PriorityReason] = []
        score = 0

        priority = self._normalize_priority(task.priority)

        if priority in self._EXPLICIT_PRIORITY_POINTS:
            points = self._EXPLICIT_PRIORITY_POINTS[priority]
            score += points
            reasons.append(
                PriorityReason(
                    code=PriorityReasonCode.EXPLICIT_PRIORITY,
                    points=points,
                    message=f"Explicit priority: {priority}.",
                )
            )

        due_reason, due_points = self._due_reason(
            due_at=task.due_at,
            window_start_utc=window_start_utc,
            window_end_utc=window_end_utc,
        )

        score += due_points

        if due_reason is not None:
            reasons.append(due_reason)

        if task.commitment_id is not None:
            score += self._LINKED_COMMITMENT_POINTS
            reasons.append(
                PriorityReason(
                    code=PriorityReasonCode.LINKED_COMMITMENT,
                    points=self._LINKED_COMMITMENT_POINTS,
                    message="Linked to a commitment.",
                )
            )

        return PrioritizedItem(
            item_type=PriorityItemType.TASK,
            item_id=task.id,
            title=task.description,
            score=score,
            reasons=tuple(reasons),
        )

    def _prioritize_commitment(
        self,
        commitment: DailyCommitment,
        *,
        window_start_utc: datetime,
        window_end_utc: datetime,
    ) -> PrioritizedItem:
        reasons: list[PriorityReason] = []

        due_reason, due_points = self._due_reason(
            due_at=commitment.deadline_at,
            window_start_utc=window_start_utc,
            window_end_utc=window_end_utc,
        )

        if due_reason is not None:
            reasons.append(due_reason)

        return PrioritizedItem(
            item_type=PriorityItemType.COMMITMENT,
            item_id=commitment.id,
            title=commitment.description,
            score=due_points,
            reasons=tuple(reasons),
        )

    @staticmethod
    def _normalize_priority(priority: str | None) -> str | None:
        if priority is None:
            return None

        normalized = priority.strip().casefold()

        return normalized or None

    def _due_reason(
        self,
        *,
        due_at: datetime | None,
        window_start_utc: datetime,
        window_end_utc: datetime,
    ) -> tuple[PriorityReason | None, int]:
        if due_at is None:
            return (
                PriorityReason(
                    code=PriorityReasonCode.NO_DUE_DATE,
                    points=self._NO_DUE_DATE_POINTS,
                    message="No due date.",
                ),
                self._NO_DUE_DATE_POINTS,
            )

        midpoint = window_start_utc + (
            (window_end_utc - window_start_utc) / 2
        )

        if due_at <= midpoint:
            return (
                PriorityReason(
                    code=PriorityReasonCode.DUE_SOON,
                    points=self._DUE_SOON_POINTS,
                    message="Due during the earlier part of the daily window.",
                ),
                self._DUE_SOON_POINTS,
            )

        return (
            PriorityReason(
                code=PriorityReasonCode.DUE_LATER,
                points=self._DUE_LATER_POINTS,
                message="Due during the later part of the daily window.",
            ),
            self._DUE_LATER_POINTS,
        )