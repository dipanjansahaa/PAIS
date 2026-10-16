"""Deterministic daily intelligence service."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.commitment import Commitment
from app.database.models.decision import Decision
from app.database.models.person import Person
from app.database.models.project import Project
from app.database.models.risk import Risk
from app.database.models.task import Task
from app.daily.models import (
    DailyChange,
    DailyCommitment,
    DailyDecision,
    DailySnapshot,
    DailyTask,
)


class DailyIntelligenceService:
    """Build deterministic daily intelligence from persisted state."""

    async def build_snapshot(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        day: date,
        timezone_name: str,
    ) -> DailySnapshot:
        """Build a deterministic daily snapshot for a user's local day."""

        window_start_utc, window_end_utc = self._utc_day_window(
            day=day,
            timezone_name=timezone_name,
        )

        tasks = await self._get_open_tasks(
            session,
            user_id=user_id,
            window_start_utc=window_start_utc,
            window_end_utc=window_end_utc,
        )

        commitments = await self._get_open_commitments(
            session,
            user_id=user_id,
            window_start_utc=window_start_utc,
            window_end_utc=window_end_utc,
        )

        decisions = await self._get_recent_decisions(
            session,
            user_id=user_id,
            window_start_utc=window_start_utc,
            window_end_utc=window_end_utc,
        )

        changes = await self._get_recent_changes(
            session,
            user_id=user_id,
            window_start_utc=window_start_utc,
            window_end_utc=window_end_utc,
        )

        return DailySnapshot(
            day=day,
            timezone_name=timezone_name,
            window_start_utc=window_start_utc,
            window_end_utc=window_end_utc,
            open_tasks=tuple(tasks),
            open_commitments=tuple(commitments),
            recent_decisions=tuple(decisions),
            recent_changes=tuple(changes),
        )

    @staticmethod
    def _utc_day_window(
        *,
        day: date,
        timezone_name: str,
    ) -> tuple[datetime, datetime]:
        """Convert a local calendar day into a UTC half-open interval."""

        try:
            zone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(
                f"Unknown timezone: {timezone_name}"
            ) from exc

        local_start = datetime.combine(
            day,
            time.min,
            tzinfo=zone,
        )

        local_end = local_start + timedelta(days=1)

        return (
            DailyIntelligenceService._as_database_utc(
                local_start.astimezone(timezone.utc)
            ),
            DailyIntelligenceService._as_database_utc(
                local_end.astimezone(timezone.utc)
            ),
        )

    @staticmethod
    async def _get_open_tasks(
        session: AsyncSession,
        *,
        user_id: UUID,
        window_start_utc: datetime,
        window_end_utc: datetime,
    ) -> list[DailyTask]:
        """Load all open tasks relevant to the daily context."""

        result = await session.scalars(
            select(Task)
            .where(
                Task.user_id == user_id,
                Task.status == "open",
                (
                    and_(
                        Task.due_at >= window_start_utc,
                        Task.due_at < window_end_utc,
                    )
                    | Task.due_at.is_(None)
                ),
            )
            .order_by(
                Task.due_at.asc().nulls_last(),
                Task.created_at.asc(),
            )
        )

        return [
            DailyTask(
                id=task.id,
                description=task.description,
                owner=task.owner,
                due_at=task.due_at,
                priority=task.priority,
                status=task.status,
                project_id=task.project_id,
                commitment_id=task.commitment_id,
            )
            for task in result.all()
        ]

    @staticmethod
    async def _get_open_commitments(
        session: AsyncSession,
        *,
        user_id: UUID,
        window_start_utc: datetime,
        window_end_utc: datetime,
    ) -> list[DailyCommitment]:
        """Load all open commitments relevant to the daily context."""

        result = await session.scalars(
            select(Commitment)
            .where(
                Commitment.user_id == user_id,
                Commitment.status == "open",
                (
                    and_(
                        Commitment.deadline_at >= window_start_utc,
                        Commitment.deadline_at < window_end_utc,
                    )
                    | Commitment.deadline_at.is_(None)
                ),
            )
            .order_by(
                Commitment.deadline_at.asc().nulls_last(),
                Commitment.created_at.asc(),
            )
        )

        return [
            DailyCommitment(
                id=commitment.id,
                description=commitment.description,
                owner=commitment.owner,
                deadline_at=commitment.deadline_at,
                status=commitment.status,
                project_id=commitment.project_id,
            )
            for commitment in result.all()
        ]

    @staticmethod
    async def _get_recent_decisions(
        session: AsyncSession,
        *,
        user_id: UUID,
        window_start_utc: datetime,
        window_end_utc: datetime,
    ) -> list[DailyDecision]:
        """Load decisions updated during the requested local day."""

        result = await session.scalars(
            select(Decision)
            .where(
                Decision.user_id == user_id,
                Decision.updated_at >= window_start_utc,
                Decision.updated_at < window_end_utc,
            )
            .order_by(Decision.updated_at.desc())
        )

        return [
            DailyDecision(
                id=decision.id,
                title=decision.title,
                description=decision.description,
                decision_date=decision.decision_date,
                status=decision.status,
                project_id=decision.project_id,
            )
            for decision in result.all()
        ]

    @staticmethod
    async def _get_recent_changes(
        session: AsyncSession,
        *,
        user_id: UUID,
        window_start_utc: datetime,
        window_end_utc: datetime,
    ) -> list[DailyChange]:
        """Load structured entities updated during the requested local day."""

        changes: list[DailyChange] = []

        task_result = await session.scalars(
            select(Task)
            .where(
                Task.user_id == user_id,
                Task.updated_at >= window_start_utc,
                Task.updated_at < window_end_utc,
            )
        )

        changes.extend(
            DailyChange(
                entity_type="task",
                entity_id=task.id,
                changed_at=task.updated_at,
            )
            for task in task_result.all()
        )

        commitment_result = await session.scalars(
            select(Commitment)
            .where(
                Commitment.user_id == user_id,
                Commitment.updated_at >= window_start_utc,
                Commitment.updated_at < window_end_utc,
            )
        )

        changes.extend(
            DailyChange(
                entity_type="commitment",
                entity_id=commitment.id,
                changed_at=commitment.updated_at,
            )
            for commitment in commitment_result.all()
        )

        decision_result = await session.scalars(
            select(Decision)
            .where(
                Decision.user_id == user_id,
                Decision.updated_at >= window_start_utc,
                Decision.updated_at < window_end_utc,
            )
        )

        changes.extend(
            DailyChange(
                entity_type="decision",
                entity_id=decision.id,
                changed_at=decision.updated_at,
            )
            for decision in decision_result.all()
        )

        project_result = await session.scalars(
            select(Project)
            .where(
                Project.user_id == user_id,
                Project.updated_at >= window_start_utc,
                Project.updated_at < window_end_utc,
            )
        )

        changes.extend(
            DailyChange(
                entity_type="project",
                entity_id=project.id,
                changed_at=project.updated_at,
            )
            for project in project_result.all()
        )

        person_result = await session.scalars(
            select(Person)
            .where(
                Person.user_id == user_id,
                Person.updated_at >= window_start_utc,
                Person.updated_at < window_end_utc,
            )
        )

        changes.extend(
            DailyChange(
                entity_type="person",
                entity_id=person.id,
                changed_at=person.updated_at,
            )
            for person in person_result.all()
        )

        risk_result = await session.scalars(
            select(Risk)
            .where(
                Risk.user_id == user_id,
                Risk.updated_at >= window_start_utc,
                Risk.updated_at < window_end_utc,
            )
        )

        changes.extend(
            DailyChange(
                entity_type="risk",
                entity_id=risk.id,
                changed_at=risk.updated_at,
            )
            for risk in risk_result.all()
        )

        return sorted(
            changes,
            key=lambda change: change.changed_at,
            reverse=True,
        )

    @staticmethod
    def _as_database_utc(value: datetime) -> datetime:
        """Convert an aware UTC datetime to the database's naive UTC format."""

        if value.tzinfo is None:
            raise ValueError("Expected timezone-aware datetime")

        return value.astimezone(timezone.utc).replace(tzinfo=None)