"""Structured context builder for daily intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from app.daily.models import (
    DailyChange,
    DailyDecision,
    DailySnapshot,
)
from app.daily.priority import PrioritizedItem

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.daily.enrichment import (
        DailyPersonContext,
        DailyProjectContext,
        DailyRiskContext,
    )


@dataclass(frozen=True, slots=True)
class DailyIntelligenceContext:
    """Structured context prepared for downstream daily intelligence generation."""

    day: date
    timezone_name: str
    window_start_utc: datetime
    window_end_utc: datetime
    prioritized_items: tuple[PrioritizedItem, ...]
    recent_decisions: tuple[DailyDecision, ...]
    recent_changes: tuple[DailyChange, ...]
    recent_projects: tuple["DailyProjectContext", ...] = ()
    recent_people: tuple["DailyPersonContext", ...] = ()
    recent_risks: tuple["DailyRiskContext", ...] = ()


class DailyContextBuilder:
    """Build deterministic structured context from a daily snapshot."""

    def build(
        self,
        snapshot: DailySnapshot,
        prioritized_items: tuple[PrioritizedItem, ...],
    ) -> DailyIntelligenceContext:
        """Build downstream context without generating or interpreting content."""

        return DailyIntelligenceContext(
            day=snapshot.day,
            timezone_name=snapshot.timezone_name,
            window_start_utc=snapshot.window_start_utc,
            window_end_utc=snapshot.window_end_utc,
            prioritized_items=prioritized_items,
            recent_decisions=snapshot.recent_decisions,
            recent_changes=snapshot.recent_changes,
        )