"""Read service for persisted structured intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models.commitment import Commitment
from app.database.models.decision import Decision
from app.database.models.person import Person
from app.database.models.project import Project
from app.database.models.risk import Risk
from app.database.models.task import Task


@dataclass(frozen=True, slots=True)
class IntelligenceSnapshot:
    """Persisted structured intelligence for one user."""

    tasks: tuple[Task, ...]
    commitments: tuple[Commitment, ...]
    decisions: tuple[Decision, ...]
    projects: tuple[Project, ...]
    people: tuple[Person, ...]
    risks: tuple[Risk, ...]


class IntelligenceReadService:
    """Read persisted structured intelligence."""

    async def get_snapshot(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
    ) -> IntelligenceSnapshot:
        """Return all structured intelligence owned by the user."""

        tasks = (
            await session.scalars(
                select(Task)
                .options(
                    selectinload(Task.sources),
                )
                .where(Task.user_id == user_id)
                .order_by(Task.created_at.desc())
            )
        ).all()

        commitments = (
            await session.scalars(
                select(Commitment)
                .options(
                    selectinload(Commitment.sources),
                )
                .where(Commitment.user_id == user_id)
                .order_by(Commitment.created_at.desc())
            )
        ).all()

        decisions = (
            await session.scalars(
                select(Decision)
                .options(
                    selectinload(Decision.sources),
                )
                .where(Decision.user_id == user_id)
                .order_by(Decision.created_at.desc())
            )
        ).all()

        projects = (
            await session.scalars(
                select(Project)
                .options(
                    selectinload(Project.sources),
                )
                .where(Project.user_id == user_id)
                .order_by(Project.created_at.desc())
            )
        ).all()

        people = (
            await session.scalars(
                select(Person)
                .options(
                    selectinload(Person.sources),
                )
                .where(Person.user_id == user_id)
                .order_by(Person.created_at.desc())
            )
        ).all()

        risks = (
            await session.scalars(
                select(Risk)
                .options(
                    selectinload(Risk.sources),
                )
                .where(Risk.user_id == user_id)
                .order_by(Risk.created_at.desc())
            )
        ).all()

        return IntelligenceSnapshot(
            tasks=tuple(tasks),
            commitments=tuple(commitments),
            decisions=tuple(decisions),
            projects=tuple(projects),
            people=tuple(people),
            risks=tuple(risks),
        )