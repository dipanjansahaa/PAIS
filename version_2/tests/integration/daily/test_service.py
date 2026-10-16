"""Integration tests for daily intelligence service."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.daily.service import DailyIntelligenceService
from app.database.models.commitment import Commitment
from app.database.models.decision import Decision
from app.database.models.person import Person
from app.database.models.project import Project
from app.database.models.risk import Risk
from app.database.models.task import Task
from app.database.models.user import User


@pytest.mark.integration
@pytest.mark.asyncio
async def test_build_snapshot_respects_user_isolation(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"daily-{uuid4()}@example.com",
        display_name="Daily User",
    )

    other_user = User(
        email=f"daily-other-{uuid4()}@example.com",
        display_name="Other Daily User",
    )

    db_session.add_all([user, other_user])
    await db_session.flush()

    own_task = Task(
        user_id=user.id,
        description="Own task",
        status="open",
    )

    foreign_task = Task(
        user_id=other_user.id,
        description="Foreign task",
        status="open",
    )

    own_commitment = Commitment(
        user_id=user.id,
        description="Own commitment",
        status="open",
    )

    foreign_commitment = Commitment(
        user_id=other_user.id,
        description="Foreign commitment",
        status="open",
    )

    db_session.add_all(
        [
            own_task,
            foreign_task,
            own_commitment,
            foreign_commitment,
        ]
    )
    await db_session.flush()

    snapshot = await DailyIntelligenceService().build_snapshot(
        db_session,
        user_id=user.id,
        day=datetime.now(timezone.utc).date(),
        timezone_name="UTC",
    )

    assert [task.id for task in snapshot.open_tasks] == [
        own_task.id,
    ]

    assert [
        commitment.id
        for commitment in snapshot.open_commitments
    ] == [
        own_commitment.id,
    ]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_build_snapshot_uses_local_day_boundaries(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"daily-boundary-{uuid4()}@example.com",
        display_name="Daily Boundary User",
    )

    db_session.add(user)
    await db_session.flush()

    task_before_local_day = Task(
        user_id=user.id,
        description="Before local day",
        status="open",
        due_at=datetime(
            2026,
            10,
            1,
            18,
            29,
            59,
            # tzinfo=timezone.utc,
        ),
    )

    task_at_local_midnight = Task(
        user_id=user.id,
        description="At local midnight",
        status="open",
        due_at=datetime(
            2026,
            10,
            1,
            18,
            30,
            # tzinfo=timezone.utc,
        ),
    )

    task_at_next_local_midnight = Task(
        user_id=user.id,
        description="At next local midnight",
        status="open",
        due_at=datetime(
            2026,
            10,
            2,
            18,
            30,
            # tzinfo=timezone.utc,
        ),
    )

    db_session.add_all(
        [
            task_before_local_day,
            task_at_local_midnight,
            task_at_next_local_midnight,
        ]
    )
    await db_session.flush()

    snapshot = await DailyIntelligenceService().build_snapshot(
        db_session,
        user_id=user.id,
        day=datetime(
            2026,
            10,
            2,
            tzinfo=timezone.utc,
        ).date(),
        timezone_name="Asia/Kolkata",
    )

    task_ids = {
        task.id
        for task in snapshot.open_tasks
    }

    assert task_before_local_day.id not in task_ids
    assert task_at_local_midnight.id in task_ids
    assert task_at_next_local_midnight.id not in task_ids


@pytest.mark.integration
@pytest.mark.asyncio
async def test_build_snapshot_includes_recent_structured_changes(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"daily-changes-{uuid4()}@example.com",
        display_name="Daily Changes User",
    )

    db_session.add(user)
    await db_session.flush()

    recent_at = datetime.now(timezone.utc).replace(tzinfo=None)

    project = Project(
        user_id=user.id,
        name="Daily Project",
        updated_at=recent_at,
    )

    person = Person(
        user_id=user.id,
        name="Daily Person",
        updated_at=recent_at,
    )

    risk = Risk(
        user_id=user.id,
        title="Daily Risk",
        updated_at=recent_at,
    )

    task = Task(
        user_id=user.id,
        description="Daily Task",
        status="open",
        updated_at=recent_at,
    )

    commitment = Commitment(
        user_id=user.id,
        description="Daily Commitment",
        status="open",
        updated_at=recent_at,
    )

    decision = Decision(
        user_id=user.id,
        title="Daily Decision",
        description="Use PostgreSQL",
        status="active",
        updated_at=recent_at,
    )

    db_session.add_all(
        [
            project,
            person,
            risk,
            task,
            commitment,
            decision,
        ]
    )

    await db_session.flush()

    snapshot = await DailyIntelligenceService().build_snapshot(
        db_session,
        user_id=user.id,
        day=datetime.now(timezone.utc).date(),
        timezone_name="UTC",
    )

    entity_types = {
        change.entity_type
        for change in snapshot.recent_changes
    }

    assert {
        "project",
        "person",
        "risk",
        "task",
        "commitment",
        "decision",
    }.issubset(entity_types)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_build_snapshot_includes_recent_decisions(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"daily-decisions-{uuid4()}@example.com",
        display_name="Daily Decisions User",
    )

    db_session.add(user)
    await db_session.flush()

    recent_at = datetime.now(timezone.utc).replace(tzinfo=None)

    decision = Decision(
        user_id=user.id,
        title="Database Choice",
        description="Use PostgreSQL",
        status="active",
        updated_at=recent_at,
    )

    db_session.add(decision)
    await db_session.flush()

    snapshot = await DailyIntelligenceService().build_snapshot(
        db_session,
        user_id=user.id,
        day=datetime.now(timezone.utc).date(),
        timezone_name="UTC",
    )

    assert len(snapshot.recent_decisions) == 1
    assert snapshot.recent_decisions[0].id == decision.id
    assert snapshot.recent_decisions[0].title == "Database Choice"