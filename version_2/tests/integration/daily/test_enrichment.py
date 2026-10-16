"""Integration tests for daily entity-context enrichment."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.daily.context import DailyIntelligenceContext
from app.daily.enrichment import DailyEntityContextEnricher
from app.daily.models import DailyChange
from app.database.models.person import Person
from app.database.models.project import Project
from app.database.models.risk import Risk
from app.database.models.user import User


def _context(
    *,
    changes: tuple[DailyChange, ...],
) -> DailyIntelligenceContext:
    """Build a minimal daily context for enrichment tests."""

    window_start = datetime(
        2026,
        10,
        1,
        tzinfo=timezone.utc,
    )

    window_end = datetime(
        2026,
        10,
        2,
        tzinfo=timezone.utc,
    )

    return DailyIntelligenceContext(
        day=window_start.date(),
        timezone_name="UTC",
        window_start_utc=window_start,
        window_end_utc=window_end,
        prioritized_items=(),
        recent_decisions=(),
        recent_changes=changes,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enriches_recent_project_context(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"daily-enrichment-project-{uuid4()}@example.com",
        display_name="Daily Enrichment Project User",
    )

    db_session.add(user)
    await db_session.flush()

    changed_at = datetime(
        2026,
        10,
        1,
        12,
        30,
    )

    project = Project(
        user_id=user.id,
        name="PAIS Development",
        description="Build the PAIS system.",
        status="active",
        updated_at=changed_at,
    )

    db_session.add(project)
    await db_session.flush()

    context = _context(
        changes=(
            DailyChange(
                entity_type="project",
                entity_id=project.id,
                changed_at=changed_at,
            ),
        ),
    )

    enriched = await DailyEntityContextEnricher().enrich(
        db_session,
        user_id=user.id,
        context=context,
    )

    assert len(enriched.recent_projects) == 1

    result = enriched.recent_projects[0]

    assert result.id == project.id
    assert result.name == "PAIS Development"
    assert result.description == "Build the PAIS system."
    assert result.status == "active"
    assert result.changed_at == changed_at


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enriches_recent_person_context(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"daily-enrichment-person-{uuid4()}@example.com",
        display_name="Daily Enrichment Person User",
    )

    db_session.add(user)
    await db_session.flush()

    changed_at = datetime(
        2026,
        10,
        1,
        13,
        15,
    )

    person = Person(
        user_id=user.id,
        name="Alice Smith",
        email="alice@example.com",
        updated_at=changed_at,
    )

    db_session.add(person)
    await db_session.flush()

    context = _context(
        changes=(
            DailyChange(
                entity_type="person",
                entity_id=person.id,
                changed_at=changed_at,
            ),
        ),
    )

    enriched = await DailyEntityContextEnricher().enrich(
        db_session,
        user_id=user.id,
        context=context,
    )

    assert len(enriched.recent_people) == 1

    result = enriched.recent_people[0]

    assert result.id == person.id
    assert result.name == "Alice Smith"
    assert result.email == "alice@example.com"
    assert result.changed_at == changed_at


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enriches_recent_risk_context(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"daily-enrichment-risk-{uuid4()}@example.com",
        display_name="Daily Enrichment Risk User",
    )

    db_session.add(user)
    await db_session.flush()

    changed_at = datetime(
        2026,
        10,
        1,
        14,
        45,
    )

    risk = Risk(
        user_id=user.id,
        title="Deployment delay",
        description="Deployment may be delayed.",
        severity="high",
        updated_at=changed_at,
    )

    db_session.add(risk)
    await db_session.flush()

    context = _context(
        changes=(
            DailyChange(
                entity_type="risk",
                entity_id=risk.id,
                changed_at=changed_at,
            ),
        ),
    )

    enriched = await DailyEntityContextEnricher().enrich(
        db_session,
        user_id=user.id,
        context=context,
    )

    assert len(enriched.recent_risks) == 1

    result = enriched.recent_risks[0]

    assert result.id == risk.id
    assert result.title == "Deployment delay"
    assert result.description == "Deployment may be delayed."
    assert result.severity == "high"
    assert result.changed_at == changed_at


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enrichment_preserves_change_order(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"daily-enrichment-order-{uuid4()}@example.com",
        display_name="Daily Enrichment Order User",
    )

    db_session.add(user)
    await db_session.flush()

    first_changed_at = datetime(
        2026,
        10,
        1,
        10,
        0,
    )

    second_changed_at = datetime(
        2026,
        10,
        1,
        11,
        0,
    )

    first_project = Project(
        user_id=user.id,
        name="First Project",
        description="First project.",
        status="active",
        updated_at=first_changed_at,
    )

    second_project = Project(
        user_id=user.id,
        name="Second Project",
        description="Second project.",
        status="active",
        updated_at=second_changed_at,
    )

    db_session.add_all(
        [
            first_project,
            second_project,
        ]
    )

    await db_session.flush()

    context = _context(
        changes=(
            DailyChange(
                entity_type="project",
                entity_id=second_project.id,
                changed_at=second_changed_at,
            ),
            DailyChange(
                entity_type="project",
                entity_id=first_project.id,
                changed_at=first_changed_at,
            ),
        ),
    )

    enriched = await DailyEntityContextEnricher().enrich(
        db_session,
        user_id=user.id,
        context=context,
    )

    assert [
        project.id
        for project in enriched.recent_projects
    ] == [
        second_project.id,
        first_project.id,
    ]

    assert [
        project.changed_at
        for project in enriched.recent_projects
    ] == [
        second_changed_at,
        first_changed_at,
    ]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enrichment_ignores_missing_entities(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"daily-enrichment-missing-{uuid4()}@example.com",
        display_name="Daily Enrichment Missing User",
    )

    db_session.add(user)
    await db_session.flush()

    missing_project_id = uuid4()

    changed_at = datetime(
        2026,
        10,
        1,
        15,
        0,
    )

    context = _context(
        changes=(
            DailyChange(
                entity_type="project",
                entity_id=missing_project_id,
                changed_at=changed_at,
            ),
        ),
    )

    enriched = await DailyEntityContextEnricher().enrich(
        db_session,
        user_id=user.id,
        context=context,
    )

    assert enriched.recent_projects == ()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enrichment_enforces_user_isolation(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"daily-enrichment-owner-{uuid4()}@example.com",
        display_name="Daily Enrichment Owner",
    )

    foreign_user = User(
        email=f"daily-enrichment-foreign-{uuid4()}@example.com",
        display_name="Daily Enrichment Foreign User",
    )

    db_session.add_all(
        [
            user,
            foreign_user,
        ]
    )

    await db_session.flush()

    changed_at = datetime(
        2026,
        10,
        1,
        16,
        0,
    )

    foreign_project = Project(
        user_id=foreign_user.id,
        name="Foreign Project",
        description="Should not be visible.",
        status="active",
        updated_at=changed_at,
    )

    foreign_person = Person(
        user_id=foreign_user.id,
        name="Foreign Person",
        email="foreign@example.com",
        updated_at=changed_at,
    )

    foreign_risk = Risk(
        user_id=foreign_user.id,
        title="Foreign Risk",
        description="Should not be visible.",
        severity="high",
        updated_at=changed_at,
    )

    db_session.add_all(
        [
            foreign_project,
            foreign_person,
            foreign_risk,
        ]
    )

    await db_session.flush()

    context = _context(
        changes=(
            DailyChange(
                entity_type="project",
                entity_id=foreign_project.id,
                changed_at=changed_at,
            ),
            DailyChange(
                entity_type="person",
                entity_id=foreign_person.id,
                changed_at=changed_at,
            ),
            DailyChange(
                entity_type="risk",
                entity_id=foreign_risk.id,
                changed_at=changed_at,
            ),
        ),
    )

    enriched = await DailyEntityContextEnricher().enrich(
        db_session,
        user_id=user.id,
        context=context,
    )

    assert enriched.recent_projects == ()
    assert enriched.recent_people == ()
    assert enriched.recent_risks == ()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enrichment_preserves_existing_daily_context(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"daily-enrichment-preserve-{uuid4()}@example.com",
        display_name="Daily Enrichment Preserve User",
    )

    db_session.add(user)
    await db_session.flush()

    changed_at = datetime(
        2026,
        10,
        1,
        17,
        0,
    )

    project = Project(
        user_id=user.id,
        name="Preserved Project",
        description="Project context.",
        status="active",
        updated_at=changed_at,
    )

    db_session.add(project)
    await db_session.flush()

    context = _context(
        changes=(
            DailyChange(
                entity_type="project",
                entity_id=project.id,
                changed_at=changed_at,
            ),
        ),
    )

    enriched = await DailyEntityContextEnricher().enrich(
        db_session,
        user_id=user.id,
        context=context,
    )

    assert enriched.day == context.day
    assert enriched.timezone_name == context.timezone_name
    assert enriched.window_start_utc == context.window_start_utc
    assert enriched.window_end_utc == context.window_end_utc
    assert enriched.prioritized_items == context.prioritized_items
    assert enriched.recent_decisions == context.recent_decisions
    assert enriched.recent_changes == context.recent_changes