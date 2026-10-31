"""Regression tests for historical memory and relationship retrieval."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.database.models.memory import Memory
from app.database.models.project import Project
from app.database.models.user import User
from app.memory.service import MemoryService
from app.query.relationship_context import RelationshipContextBuilder
from app.relationships.service import RelationshipService
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def _create_user(session: AsyncSession, label: str) -> User:
    user = User(
        email=f"temporal-query-{label}-{uuid4()}@example.com",
        display_name=f"Temporal Query {label.title()} User",
    )
    session.add(user)
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_historical_memory_validity_uses_inclusive_start_and_exclusive_end(
    db_session: AsyncSession,
) -> None:
    """Start is inclusive, end is exclusive, and lifecycle status is not a proxy."""
    user = await _create_user(db_session, "memory-boundaries")
    as_of = datetime.now(UTC)

    starts_at_reference = Memory(
        user_id=user.id,
        memory_type="preference",
        content="Historical temporal boundary starts here.",
        normalized_content="historical temporal boundary starts here.",
        status="superseded",
        confidence=0.9,
        valid_from=as_of,
        valid_until=as_of + timedelta(days=1),
    )
    ends_at_reference = Memory(
        user_id=user.id,
        memory_type="preference",
        content="Historical temporal boundary ends here.",
        normalized_content="historical temporal boundary ends here.",
        status="expired",
        confidence=0.9,
        valid_from=as_of - timedelta(days=1),
        valid_until=as_of,
    )
    unknown_boundaries = Memory(
        user_id=user.id,
        memory_type="preference",
        content="Historical temporal boundary is unknown.",
        normalized_content="historical temporal boundary is unknown.",
        status="active",
        confidence=0.8,
        valid_from=None,
        valid_until=None,
    )
    db_session.add_all([starts_at_reference, ends_at_reference, unknown_boundaries])
    await db_session.flush()

    results = await MemoryService().retrieve_memories(
        db_session,
        user_id=user.id,
        query="historical temporal boundary",
        as_of=as_of,
    )

    result_ids = {memory.id for memory in results}
    assert starts_at_reference.id in result_ids
    assert ends_at_reference.id not in result_ids
    # Null boundaries are candidates, but query context must preserve uncertainty.
    assert unknown_boundaries.id in result_ids


@pytest.mark.asyncio
async def test_historical_relationship_validity_and_unknown_boundary_note(
    db_session: AsyncSession,
) -> None:
    """Relationship intervals use [start, end); unknown bounds are labelled."""
    user = await _create_user(db_session, "relationship-boundaries")
    source = Project(user_id=user.id, name="Temporal source")
    starts_target = Project(user_id=user.id, name="Starts at reference")
    ends_target = Project(user_id=user.id, name="Ends at reference")
    unknown_target = Project(user_id=user.id, name="Unknown validity target")
    db_session.add_all([source, starts_target, ends_target, unknown_target])
    await db_session.flush()

    as_of = datetime.now(UTC)
    relationships = RelationshipService()
    await relationships.create_relationship(
        db_session,
        user_id=user.id,
        source_type="project",
        source_id=source.id,
        relationship_type="related_to",
        target_type="project",
        target_id=starts_target.id,
        valid_from=as_of,
        valid_until=as_of + timedelta(days=1),
    )
    await relationships.create_relationship(
        db_session,
        user_id=user.id,
        source_type="project",
        source_id=source.id,
        relationship_type="related_to",
        target_type="project",
        target_id=ends_target.id,
        valid_from=as_of - timedelta(days=1),
        valid_until=as_of,
    )
    await relationships.create_relationship(
        db_session,
        user_id=user.id,
        source_type="project",
        source_id=source.id,
        relationship_type="depends_on",
        target_type="project",
        target_id=unknown_target.id,
    )

    context = await RelationshipContextBuilder().build(
        db_session,
        user_id=user.id,
        entity_type="project",
        entity_id=source.id,
        as_of=as_of,
    )

    target_labels = {relationship.target_label for relationship in context.relationships}
    assert "Starts at reference" in target_labels
    assert "Ends at reference" not in target_labels
    assert "Unknown validity target" in target_labels
    assert "validity boundaries incomplete" in context.text
    assert "not proof of indefinite validity" in context.text
