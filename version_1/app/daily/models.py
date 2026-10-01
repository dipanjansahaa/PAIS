"""Domain models for deterministic daily intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DailyTask:
    """Open task included in the daily snapshot."""

    id: UUID
    description: str
    owner: str | None
    due_at: datetime | None
    priority: str | None
    status: str
    project_id: UUID | None
    commitment_id: UUID | None


@dataclass(frozen=True, slots=True)
class DailyCommitment:
    """Open commitment included in the daily snapshot."""

    id: UUID
    description: str
    owner: str | None
    deadline_at: datetime | None
    status: str
    project_id: UUID | None


@dataclass(frozen=True, slots=True)
class DailyDecision:
    """Decision changed during the requested local day."""

    id: UUID
    title: str
    description: str
    decision_date: datetime | None
    status: str
    project_id: UUID | None


@dataclass(frozen=True, slots=True)
class DailyChange:
    """Structured entity changed during the requested local day."""

    entity_type: str
    entity_id: UUID
    changed_at: datetime


@dataclass(frozen=True, slots=True)
class DailySnapshot:
    """Deterministic structured state for one user's local day."""

    day: date
    timezone_name: str
    window_start_utc: datetime
    window_end_utc: datetime
    open_tasks: tuple[DailyTask, ...]
    open_commitments: tuple[DailyCommitment, ...]
    recent_decisions: tuple[DailyDecision, ...]
    recent_changes: tuple[DailyChange, ...]