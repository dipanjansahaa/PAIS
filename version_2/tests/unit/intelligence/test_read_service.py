"""Unit tests for the structured intelligence read service."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.database.models.commitment import (
    Commitment,
    CommitmentSource,
)
from app.database.models.decision import Decision, DecisionSource
from app.database.models.person import Person, PersonSource
from app.database.models.project import Project, ProjectSource
from app.database.models.risk import Risk, RiskSource
from app.database.models.task import Task, TaskSource
from app.intelligence.read_service import IntelligenceReadService


class FakeScalarResult:
    """Minimal scalar result used by the unit test."""

    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class FakeSession:
    """Minimal async session returning predetermined query results."""

    def __init__(self, results):
        self._results = iter(results)
        self.statements = []

    async def scalars(self, statement):
        self.statements.append(statement)
        return FakeScalarResult(next(self._results))


@pytest.mark.asyncio
async def test_get_snapshot_returns_all_intelligence_categories() -> None:
    user_id = uuid4()

    task_id = uuid4()
    task_chunk_id = uuid4()

    commitment_id = uuid4()
    commitment_chunk_id = uuid4()

    decision_id = uuid4()
    decision_chunk_id = uuid4()

    project_id = uuid4()
    project_chunk_id = uuid4()

    person_id = uuid4()
    person_chunk_id = uuid4()

    risk_id = uuid4()
    risk_chunk_id = uuid4()

    now = datetime.now(timezone.utc)

    task = Task(
        id=task_id,
        user_id=user_id,
        description="Review deployment",
        owner="Dipanjan",
        due_at=now,
        priority="high",
        status="open",
        sources=[
            TaskSource(
                task_id=task_id,
                chunk_id=task_chunk_id,
            ),
        ],
    )

    commitment = Commitment(
        id=commitment_id,
        user_id=user_id,
        description="Complete deployment review",
        owner="Dipanjan",
        deadline_at=now,
        status="open",
        sources=[
            CommitmentSource(
                commitment_id=commitment_id,
                chunk_id=commitment_chunk_id,
            ),
        ],
    )

    decision = Decision(
        id=decision_id,
        user_id=user_id,
        title="Use PostgreSQL",
        description="Use PostgreSQL for PAIS persistence.",
        decision_date=now,
        status="active",
        sources=[
            DecisionSource(
                decision_id=decision_id,
                chunk_id=decision_chunk_id,
            ),
        ],
    )

    project = Project(
        id=project_id,
        user_id=user_id,
        name="PAIS V1",
        description="Personal intelligence system.",
        status="active",
        sources=[
            ProjectSource(
                project_id=project_id,
                chunk_id=project_chunk_id,
            ),
        ],
    )

    person = Person(
        id=person_id,
        user_id=user_id,
        name="Dipanjan",
        email="dipanjan@example.com",
        sources=[
            PersonSource(
                person_id=person_id,
                chunk_id=person_chunk_id,
            ),
        ],
    )

    risk = Risk(
        id=risk_id,
        user_id=user_id,
        title="Deployment risk",
        description="Deployment may require additional validation.",
        severity="medium",
        sources=[
            RiskSource(
                risk_id=risk_id,
                chunk_id=risk_chunk_id,
            ),
        ],
    )

    session = FakeSession(
        [
            [task],
            [commitment],
            [decision],
            [project],
            [person],
            [risk],
        ]
    )

    service = IntelligenceReadService()

    snapshot = await service.get_snapshot(
        session,
        user_id=user_id,
    )

    assert snapshot.tasks == (task,)
    assert snapshot.commitments == (commitment,)
    assert snapshot.decisions == (decision,)
    assert snapshot.projects == (project,)
    assert snapshot.people == (person,)
    assert snapshot.risks == (risk,)

    assert snapshot.tasks[0].sources[0].chunk_id == task_chunk_id
    assert (
        snapshot.commitments[0].sources[0].chunk_id
        == commitment_chunk_id
    )
    assert (
        snapshot.decisions[0].sources[0].chunk_id
        == decision_chunk_id
    )
    assert (
        snapshot.projects[0].sources[0].chunk_id
        == project_chunk_id
    )
    assert (
        snapshot.people[0].sources[0].chunk_id
        == person_chunk_id
    )
    assert snapshot.risks[0].sources[0].chunk_id == risk_chunk_id

    assert len(session.statements) == 6


@pytest.mark.asyncio
async def test_get_snapshot_handles_empty_intelligence() -> None:
    session = FakeSession(
        [
            [],
            [],
            [],
            [],
            [],
            [],
        ]
    )

    service = IntelligenceReadService()

    snapshot = await service.get_snapshot(
        session,
        user_id=uuid4(),
    )

    assert snapshot.tasks == ()
    assert snapshot.commitments == ()
    assert snapshot.decisions == ()
    assert snapshot.projects == ()
    assert snapshot.people == ()
    assert snapshot.risks == ()

    assert len(session.statements) == 6