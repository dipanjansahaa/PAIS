
"""Persistence orchestration for extracted structured intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.commitments.service import CommitmentService
from app.decisions.service import DecisionService
from app.intelligence.models import StructuredIntelligence
from app.people.service import PersonService
from app.projects.service import ProjectService
from app.risks.service import RiskService
from app.tasks.service import TaskService


@dataclass(frozen=True, slots=True)
class IntelligencePersistenceResult:
    """Summary of structured intelligence persistence."""

    projects: int = 0
    people: int = 0
    risks: int = 0
    commitments: int = 0
    tasks: int = 0
    decisions: int = 0
    unsupported_follow_ups: int = 0
    unsupported_deadlines: int = 0


class IntelligencePersistenceService:
    """Persist supported intelligence through existing domain services."""

    def __init__(
        self,
        *,
        project_service: ProjectService | None = None,
        person_service: PersonService | None = None,
        risk_service: RiskService | None = None,
        commitment_service: CommitmentService | None = None,
        task_service: TaskService | None = None,
        decision_service: DecisionService | None = None,
    ) -> None:
        self.project_service = project_service or ProjectService()
        self.person_service = person_service or PersonService()
        self.risk_service = risk_service or RiskService()
        self.commitment_service = (
            commitment_service or CommitmentService()
        )
        self.task_service = task_service or TaskService()
        self.decision_service = decision_service or DecisionService()

    async def persist(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        intelligence: StructuredIntelligence,
    ) -> IntelligencePersistenceResult:
        """Persist supported categories and retain source provenance.

        This method does not commit or roll back the session. The caller
        owns the transaction and must roll it back if persistence fails.
        """

        counts = {
            "projects": 0,
            "people": 0,
            "risks": 0,
            "commitments": 0,
            "tasks": 0,
            "decisions": 0,
        }

        for candidate in intelligence.projects:
            await self.project_service.create_from_candidate(
                session,
                user_id=user_id,
                candidate=candidate,
            )
            counts["projects"] += 1

        for candidate in intelligence.people:
            await self.person_service.create_from_candidate(
                session,
                user_id=user_id,
                candidate=candidate,
            )
            counts["people"] += 1

        for candidate in intelligence.risks:
            await self.risk_service.create_from_candidate(
                session,
                user_id=user_id,
                candidate=candidate,
            )
            counts["risks"] += 1

        for candidate in intelligence.commitments:
            await self.commitment_service.create_from_candidate(
                session,
                user_id=user_id,
                candidate=candidate,
            )
            counts["commitments"] += 1

        for candidate in intelligence.tasks:
            await self.task_service.create_from_candidate(
                session,
                user_id=user_id,
                candidate=candidate,
            )
            counts["tasks"] += 1

        for candidate in intelligence.decisions:
            await self.decision_service.create_from_candidate(
                session,
                user_id=user_id,
                candidate=candidate,
            )
            counts["decisions"] += 1

        await session.flush()

        return IntelligencePersistenceResult(
            **counts,
            unsupported_follow_ups=len(intelligence.follow_ups),
            unsupported_deadlines=len(intelligence.deadlines),
        )
