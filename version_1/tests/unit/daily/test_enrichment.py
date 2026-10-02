"""Unit tests for daily entity-context enrichment."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.daily.context import DailyIntelligenceContext
from app.daily.enrichment import (
    DailyEntityContext,
    DailyEntityContextEnricher,
    DailyPersonContext,
    DailyProjectContext,
    DailyRiskContext,
)
from app.daily.models import DailyChange
from app.database.models.person import Person
from app.database.models.project import Project
from app.database.models.risk import Risk

from unittest.mock import AsyncMock, MagicMock


def _change(
    *,
    entity_type: str,
    entity_id=None,
    changed_at: datetime | None = None,
) -> DailyChange:
    return DailyChange(
        entity_type=entity_type,
        entity_id=entity_id or uuid4(),
        changed_at=changed_at or datetime(2026, 10, 1, 12, 0),
    )


def _context(
    *,
    changes: tuple[DailyChange, ...] = (),
) -> DailyIntelligenceContext:
    return DailyIntelligenceContext(
        day=datetime(2026, 10, 1).date(),
        timezone_name="UTC",
        window_start_utc=datetime(2026, 10, 1, 0, 0),
        window_end_utc=datetime(2026, 10, 2, 0, 0),
        prioritized_items=(),
        recent_decisions=(),
        recent_changes=changes,
    )


def _scalars_result(items):
    result = MagicMock()
    result.all.return_value = items
    return result


def test_changes_by_type_filters_and_preserves_order() -> None:
    first_project_id = uuid4()
    person_id = uuid4()
    second_project_id = uuid4()

    changes = (
        _change(
            entity_type="project",
            entity_id=first_project_id,
        ),
        _change(
            entity_type="person",
            entity_id=person_id,
        ),
        _change(
            entity_type="project",
            entity_id=second_project_id,
        ),
    )

    result = DailyEntityContextEnricher._changes_by_type(
        changes,
        "project",
    )

    assert result == (
        changes[0],
        changes[2],
    )


def test_changes_by_type_returns_empty_tuple_when_type_absent() -> None:
    changes = (
        _change(entity_type="project"),
        _change(entity_type="person"),
    )

    result = DailyEntityContextEnricher._changes_by_type(
        changes,
        "risk",
    )

    assert result == ()


@pytest.mark.asyncio
async def test_load_projects_returns_empty_without_query_for_empty_ids() -> None:
    session = AsyncMock()

    result = await DailyEntityContextEnricher._load_projects(
        session,
        user_id=uuid4(),
        entity_ids=(),
        changes=(),
    )

    assert result == ()
    session.scalars.assert_not_awaited()


@pytest.mark.asyncio
async def test_load_projects_maps_entities_and_preserves_change_order() -> None:
    session = AsyncMock()

    user_id = uuid4()
    first_id = uuid4()
    second_id = uuid4()

    first_changed_at = datetime(2026, 10, 1, 10, 0)
    second_changed_at = datetime(2026, 10, 1, 11, 0)

    first_project = Project(
        id=first_id,
        user_id=user_id,
        name="First Project",
        description="First description",
        status="active",
    )

    second_project = Project(
        id=second_id,
        user_id=user_id,
        name="Second Project",
        description="Second description",
        status="paused",
    )

    session.scalars.return_value = _scalars_result(
        [
            first_project,
            second_project,
        ]
    )

    changes = (
        _change(
            entity_type="project",
            entity_id=second_id,
            changed_at=second_changed_at,
        ),
        _change(
            entity_type="project",
            entity_id=first_id,
            changed_at=first_changed_at,
        ),
    )

    result = await DailyEntityContextEnricher._load_projects(
        session,
        user_id=user_id,
        entity_ids=(second_id, first_id),
        changes=changes,
    )

    assert result == (
        DailyProjectContext(
            id=second_id,
            name="Second Project",
            description="Second description",
            status="paused",
            changed_at=second_changed_at,
        ),
        DailyProjectContext(
            id=first_id,
            name="First Project",
            description="First description",
            status="active",
            changed_at=first_changed_at,
        ),
    )


@pytest.mark.asyncio
async def test_load_people_returns_empty_without_query_for_empty_ids() -> None:
    session = AsyncMock()

    result = await DailyEntityContextEnricher._load_people(
        session,
        user_id=uuid4(),
        entity_ids=(),
        changes=(),
    )

    assert result == ()
    session.scalars.assert_not_awaited()


@pytest.mark.asyncio
async def test_load_people_maps_entities_and_preserves_change_order() -> None:
    session = AsyncMock()

    user_id = uuid4()
    person_id = uuid4()
    changed_at = datetime(2026, 10, 1, 12, 30)

    person = Person(
        id=person_id,
        user_id=user_id,
        name="Alice Smith",
        email="alice@example.com",
    )

    session.scalars.return_value = _scalars_result([person])

    changes = (
        _change(
            entity_type="person",
            entity_id=person_id,
            changed_at=changed_at,
        ),
    )

    result = await DailyEntityContextEnricher._load_people(
        session,
        user_id=user_id,
        entity_ids=(person_id,),
        changes=changes,
    )

    assert result == (
        DailyPersonContext(
            id=person_id,
            name="Alice Smith",
            email="alice@example.com",
            changed_at=changed_at,
        ),
    )


@pytest.mark.asyncio
async def test_load_risks_returns_empty_without_query_for_empty_ids() -> None:
    session = AsyncMock()

    result = await DailyEntityContextEnricher._load_risks(
        session,
        user_id=uuid4(),
        entity_ids=(),
        changes=(),
    )

    assert result == ()
    session.scalars.assert_not_awaited()


@pytest.mark.asyncio
async def test_load_risks_maps_entities_and_preserves_change_order() -> None:
    session = AsyncMock()

    user_id = uuid4()
    risk_id = uuid4()
    changed_at = datetime(2026, 10, 1, 14, 0)

    risk = Risk(
        id=risk_id,
        user_id=user_id,
        title="Deployment Risk",
        description="Deployment may be delayed.",
        severity="high",
    )

    session.scalars.return_value = _scalars_result([risk])

    changes = (
        _change(
            entity_type="risk",
            entity_id=risk_id,
            changed_at=changed_at,
        ),
    )

    result = await DailyEntityContextEnricher._load_risks(
        session,
        user_id=user_id,
        entity_ids=(risk_id,),
        changes=changes,
    )

    assert result == (
        DailyRiskContext(
            id=risk_id,
            title="Deployment Risk",
            description="Deployment may be delayed.",
            severity="high",
            changed_at=changed_at,
        ),
    )


@pytest.mark.asyncio
async def test_enrich_preserves_existing_context_and_adds_entity_context() -> None:
    session = AsyncMock()

    user_id = uuid4()
    project_id = uuid4()
    changed_at = datetime(2026, 10, 1, 15, 0)

    project = Project(
        id=project_id,
        user_id=user_id,
        name="PAIS",
        description="Personal intelligence system.",
        status="active",
    )

    session.scalars.side_effect = [
        _scalars_result([project]),
        _scalars_result([]),
        _scalars_result([]),
    ]

    original = _context(
        changes=(
            _change(
                entity_type="project",
                entity_id=project_id,
                changed_at=changed_at,
            ),
        ),
    )

    result = await DailyEntityContextEnricher().enrich(
        session,
        user_id=user_id,
        context=original,
    )

    assert result.day == original.day
    assert result.timezone_name == original.timezone_name
    assert result.window_start_utc == original.window_start_utc
    assert result.window_end_utc == original.window_end_utc
    assert result.prioritized_items == original.prioritized_items
    assert result.recent_decisions == original.recent_decisions
    assert result.recent_changes == original.recent_changes

    assert result.recent_projects == (
        DailyProjectContext(
            id=project_id,
            name="PAIS",
            description="Personal intelligence system.",
            status="active",
            changed_at=changed_at,
        ),
    )
    assert result.recent_people == ()
    assert result.recent_risks == ()


def test_daily_entity_context_is_structured_and_immutable() -> None:
    context = DailyEntityContext(
        projects=(),
        people=(),
        risks=(),
    )

    assert context.projects == ()
    assert context.people == ()
    assert context.risks == ()

    with pytest.raises(AttributeError):
        context.projects = ()  # type: ignore[misc]