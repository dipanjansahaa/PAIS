"""Entity-context enrichment for daily intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.person import Person
from app.database.models.project import Project
from app.database.models.risk import Risk
from app.daily.context import DailyIntelligenceContext
from app.daily.models import DailyChange


@dataclass(frozen=True, slots=True)
class DailyProjectContext:
    """Project context associated with a recent daily change."""

    id: UUID
    name: str
    description: str | None
    status: str
    changed_at: datetime


@dataclass(frozen=True, slots=True)
class DailyPersonContext:
    """Person context associated with a recent daily change."""

    id: UUID
    name: str
    email: str | None
    changed_at: datetime


@dataclass(frozen=True, slots=True)
class DailyRiskContext:
    """Risk context associated with a recent daily change."""

    id: UUID
    title: str
    description: str | None
    severity: str | None
    changed_at: datetime


@dataclass(frozen=True, slots=True)
class DailyEntityContext:
    """Enriched project, person, and risk context for daily intelligence."""

    projects: tuple[DailyProjectContext, ...]
    people: tuple[DailyPersonContext, ...]
    risks: tuple[DailyRiskContext, ...]


class DailyEntityContextEnricher:
    """Resolve recent entity changes into user-owned structured context."""

    async def enrich(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        context: DailyIntelligenceContext,
    ) -> DailyIntelligenceContext:
        """Enrich daily context with current project, person, and risk details."""

        entity_context = await self._load_entity_context(
            session,
            user_id=user_id,
            changes=context.recent_changes,
        )

        return context.__class__(
            day=context.day,
            timezone_name=context.timezone_name,
            window_start_utc=context.window_start_utc,
            window_end_utc=context.window_end_utc,
            prioritized_items=context.prioritized_items,
            recent_decisions=context.recent_decisions,
            recent_changes=context.recent_changes,
            recent_projects=entity_context.projects,
            recent_people=entity_context.people,
            recent_risks=entity_context.risks,
        )

    async def _load_entity_context(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        changes: tuple[DailyChange, ...],
    ) -> DailyEntityContext:
        """Load only the entities referenced by recent changes."""

        project_changes = self._changes_by_type(changes, "project")
        person_changes = self._changes_by_type(changes, "person")
        risk_changes = self._changes_by_type(changes, "risk")

        project_ids = tuple(change.entity_id for change in project_changes)
        person_ids = tuple(change.entity_id for change in person_changes)
        risk_ids = tuple(change.entity_id for change in risk_changes)

        projects = await self._load_projects(
            session,
            user_id=user_id,
            entity_ids=project_ids,
            changes=project_changes,
        )

        people = await self._load_people(
            session,
            user_id=user_id,
            entity_ids=person_ids,
            changes=person_changes,
        )

        risks = await self._load_risks(
            session,
            user_id=user_id,
            entity_ids=risk_ids,
            changes=risk_changes,
        )

        return DailyEntityContext(
            projects=projects,
            people=people,
            risks=risks,
        )

    @staticmethod
    def _changes_by_type(
        changes: tuple[DailyChange, ...],
        entity_type: str,
    ) -> tuple[DailyChange, ...]:
        """Return changes for one entity type, preserving snapshot order."""

        return tuple(
            change
            for change in changes
            if change.entity_type == entity_type
        )

    @staticmethod
    async def _load_projects(
        session: AsyncSession,
        *,
        user_id: UUID,
        entity_ids: tuple[UUID, ...],
        changes: tuple[DailyChange, ...],
    ) -> tuple[DailyProjectContext, ...]:
        """Load user-owned projects referenced by recent changes."""

        if not entity_ids:
            return ()

        result = await session.scalars(
            select(Project).where(
                Project.user_id == user_id,
                Project.id.in_(entity_ids),
            )
        )

        projects_by_id = {
            project.id: project
            for project in result.all()
        }

        return tuple(
            DailyProjectContext(
                id=project.id,
                name=project.name,
                description=project.description,
                status=project.status,
                changed_at=change.changed_at,
            )
            for change in changes
            if (project := projects_by_id.get(change.entity_id)) is not None
        )

    @staticmethod
    async def _load_people(
        session: AsyncSession,
        *,
        user_id: UUID,
        entity_ids: tuple[UUID, ...],
        changes: tuple[DailyChange, ...],
    ) -> tuple[DailyPersonContext, ...]:
        """Load user-owned people referenced by recent changes."""

        if not entity_ids:
            return ()

        result = await session.scalars(
            select(Person).where(
                Person.user_id == user_id,
                Person.id.in_(entity_ids),
            )
        )

        people_by_id = {
            person.id: person
            for person in result.all()
        }

        return tuple(
            DailyPersonContext(
                id=person.id,
                name=person.name,
                email=person.email,
                changed_at=change.changed_at,
            )
            for change in changes
            if (person := people_by_id.get(change.entity_id)) is not None
        )

    @staticmethod
    async def _load_risks(
        session: AsyncSession,
        *,
        user_id: UUID,
        entity_ids: tuple[UUID, ...],
        changes: tuple[DailyChange, ...],
    ) -> tuple[DailyRiskContext, ...]:
        """Load user-owned risks referenced by recent changes."""

        if not entity_ids:
            return ()

        result = await session.scalars(
            select(Risk).where(
                Risk.user_id == user_id,
                Risk.id.in_(entity_ids),
            )
        )

        risks_by_id = {
            risk.id: risk
            for risk in result.all()
        }

        return tuple(
            DailyRiskContext(
                id=risk.id,
                title=risk.title,
                description=risk.description,
                severity=risk.severity,
                changed_at=change.changed_at,
            )
            for change in changes
            if (risk := risks_by_id.get(change.entity_id)) is not None
        )