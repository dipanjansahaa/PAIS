"""PostgreSQL-backed integrity tests for relationship and provenance services."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.knowledge_relationship import (
    KnowledgeRelationship,
    KnowledgeRelationshipSource,
)
from app.database.models.project import Project
from app.database.models.user import User
from app.relationships.service import RelationshipService
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


async def _create_user(session: AsyncSession, label: str) -> User:
    user = User(
        email=f"relationship-{label}-{uuid4()}@example.com",
        display_name=f"Relationship {label.title()} User",
    )
    session.add(user)
    await session.flush()
    return user


async def _create_project(
    session: AsyncSession,
    *,
    user_id,
    name: str = "Relationship Integration Project",
) -> Project:
    project = Project(user_id=user_id, name=name)
    session.add(project)
    await session.flush()
    return project


async def _create_chunks(
    session: AsyncSession,
    *,
    user_id,
    count: int = 1,
) -> list[DocumentChunk]:
    document = Document(
        user_id=user_id,
        title="Relationship Evidence",
        source_type="test",
        file_name="relationship-evidence.txt",
        mime_type="text/plain",
        content_hash=uuid4().hex,
        raw_text="Evidence for relationship provenance integration tests.",
    )
    session.add(document)
    await session.flush()

    chunks = [
        DocumentChunk(
            document_id=document.id,
            chunk_index=index,
            content=f"Evidence chunk {index}.",
        )
        for index in range(count)
    ]
    session.add_all(chunks)
    await session.flush()
    return chunks


@pytest.mark.integration
@pytest.mark.asyncio
async def test_relationship_creation_is_persisted_and_idempotent(
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, "create")
    source = await _create_project(db_session, user_id=user.id, name="Source")
    target = await _create_project(db_session, user_id=user.id, name="Target")
    service = RelationshipService()

    first = await service.create_relationship(
        db_session,
        user_id=user.id,
        source_type="project",
        source_id=source.id,
        relationship_type="related_to",
        target_type="project",
        target_id=target.id,
    )
    second = await service.create_relationship(
        db_session,
        user_id=user.id,
        source_type="project",
        source_id=source.id,
        relationship_type="related_to",
        target_type="project",
        target_id=target.id,
    )

    stored = await db_session.scalar(
        select(KnowledgeRelationship).where(
            KnowledgeRelationship.user_id == user.id,
            KnowledgeRelationship.source_id == source.id,
            KnowledgeRelationship.target_id == target.id,
        )
    )
    assert first.id == second.id == stored.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_provenance_is_persisted_deduplicated_and_idempotent(
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, "provenance")
    source = await _create_project(db_session, user_id=user.id, name="Source")
    target = await _create_project(db_session, user_id=user.id, name="Target")
    chunks = await _create_chunks(db_session, user_id=user.id, count=2)
    service = RelationshipService()
    relationship = await service.create_relationship(
        db_session,
        user_id=user.id,
        source_type="project",
        source_id=source.id,
        relationship_type="references",
        target_type="project",
        target_id=target.id,
    )

    first = await service.add_sources(
        db_session,
        user_id=user.id,
        relationship_id=relationship.id,
        chunk_ids=[chunks[0].id, chunks[1].id, chunks[0].id],
    )
    second = await service.add_sources(
        db_session,
        user_id=user.id,
        relationship_id=relationship.id,
        chunk_ids=[chunks[0].id, chunks[1].id],
    )

    persisted = await db_session.scalars(
        select(KnowledgeRelationshipSource).where(
            KnowledgeRelationshipSource.relationship_id == relationship.id,
        )
    )
    persisted_rows = persisted.all()
    assert [row.chunk_id for row in first] == [chunks[0].id, chunks[1].id]
    assert [row.chunk_id for row in second] == [chunks[0].id, chunks[1].id]
    assert {row.chunk_id for row in persisted_rows} == {
        chunks[0].id,
        chunks[1].id,
    }
    assert len(persisted_rows) == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_relationship_cannot_reference_another_users_entity(
    db_session: AsyncSession,
) -> None:
    owner = await _create_user(db_session, "owner")
    foreign_user = await _create_user(db_session, "foreign")
    owned_project = await _create_project(db_session, user_id=owner.id)
    foreign_project = await _create_project(
        db_session,
        user_id=foreign_user.id,
        name="Foreign Project",
    )

    with pytest.raises(ValueError, match="does not exist or does not belong"):
        await RelationshipService().create_relationship(
            db_session,
            user_id=owner.id,
            source_type="project",
            source_id=owned_project.id,
            relationship_type="related_to",
            target_type="project",
            target_id=foreign_project.id,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_relationship_cannot_attach_another_users_chunk(
    db_session: AsyncSession,
) -> None:
    owner = await _create_user(db_session, "source-owner")
    foreign_user = await _create_user(db_session, "chunk-owner")
    source = await _create_project(db_session, user_id=owner.id, name="Source")
    target = await _create_project(db_session, user_id=owner.id, name="Target")
    foreign_chunks = await _create_chunks(db_session, user_id=foreign_user.id)
    relationship = await RelationshipService().create_relationship(
        db_session,
        user_id=owner.id,
        source_type="project",
        source_id=source.id,
        relationship_type="references",
        target_type="project",
        target_id=target.id,
    )

    with pytest.raises(ValueError, match="source chunks do not belong to the user"):
        await RelationshipService().add_sources(
            db_session,
            user_id=owner.id,
            relationship_id=relationship.id,
            chunk_ids=[foreign_chunks[0].id],
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_relationship_validity_is_persisted_and_idempotent(
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, "temporal")
    source = await _create_project(
        db_session,
        user_id=user.id,
        name="Temporal Source",
    )
    target = await _create_project(
        db_session,
        user_id=user.id,
        name="Temporal Target",
    )
    service = RelationshipService()

    valid_from = datetime(2026, 10, 1, tzinfo=UTC)
    valid_until = datetime(2026, 11, 1, tzinfo=UTC)

    first = await service.create_relationship(
        db_session,
        user_id=user.id,
        source_type="project",
        source_id=source.id,
        relationship_type="related_to",
        target_type="project",
        target_id=target.id,
        valid_from=valid_from,
        valid_until=valid_until,
    )

    second = await service.create_relationship(
        db_session,
        user_id=user.id,
        source_type="project",
        source_id=source.id,
        relationship_type="related_to",
        target_type="project",
        target_id=target.id,
        valid_from=valid_from,
        valid_until=valid_until,
    )

    await db_session.flush()
    await db_session.refresh(first)

    assert first.id == second.id
    assert first.valid_from == valid_from
    assert first.valid_until == valid_until


@pytest.mark.integration
@pytest.mark.asyncio
async def test_relationship_rejects_conflicting_validity_interval(
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, "temporal-conflict")
    source = await _create_project(
        db_session,
        user_id=user.id,
        name="Temporal Conflict Source",
    )
    target = await _create_project(
        db_session,
        user_id=user.id,
        name="Temporal Conflict Target",
    )
    service = RelationshipService()

    valid_from = datetime(2026, 10, 1, tzinfo=UTC)
    valid_until = datetime(2026, 11, 1, tzinfo=UTC)

    original = await service.create_relationship(
        db_session,
        user_id=user.id,
        source_type="project",
        source_id=source.id,
        relationship_type="related_to",
        target_type="project",
        target_id=target.id,
        valid_from=valid_from,
        valid_until=valid_until,
    )

    with pytest.raises(
        ValueError,
        match="different validity interval",
    ):
        await service.create_relationship(
            db_session,
            user_id=user.id,
            source_type="project",
            source_id=source.id,
            relationship_type="related_to",
            target_type="project",
            target_id=target.id,
            valid_from=valid_from,
            valid_until=valid_until + timedelta(days=1),
        )

    await db_session.refresh(original)

    assert original.valid_from == valid_from
    assert original.valid_until == valid_until


@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_rejects_invalid_relationship_validity_interval(
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, "invalid-temporal")
    valid_from = datetime(2026, 11, 1, tzinfo=UTC)
    invalid_valid_until = datetime(2026, 10, 1, tzinfo=UTC)

    with pytest.raises(IntegrityError):
        await db_session.execute(
            insert(KnowledgeRelationship).values(
                user_id=user.id,
                source_type="project",
                source_id=uuid4(),
                relationship_type="related_to",
                target_type="project",
                target_id=uuid4(),
                valid_from=valid_from,
                valid_until=invalid_valid_until,
            )
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_for_entity_filters_relationships_by_historical_validity(
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, "historical-validity")
    source = await _create_project(db_session, user_id=user.id, name="Historical Source")
    targets = [
        await _create_project(db_session, user_id=user.id, name=f"Historical Target {index}")
        for index in range(4)
    ]
    service = RelationshipService()
    as_of = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
    intervals = [
        (datetime(2026, 10, 1, tzinfo=UTC), datetime(2026, 11, 1, tzinfo=UTC)),
        (datetime(2026, 10, 15, 12, 0, tzinfo=UTC), datetime(2026, 10, 20, tzinfo=UTC)),
        (datetime(2026, 10, 1, tzinfo=UTC), as_of),
        (datetime(2026, 10, 16, tzinfo=UTC), None),
    ]
    created = []
    for index, (valid_from, valid_until) in enumerate(intervals):
        created.append(
            await service.create_relationship(
                db_session,
                user_id=user.id,
                source_type="project",
                source_id=source.id,
                relationship_type="related_to",
                target_type="project",
                target_id=targets[index].id,
                valid_from=valid_from,
                valid_until=valid_until,
            )
        )

    historical = await service.list_for_entity(
        db_session,
        user_id=user.id,
        entity_type="project",
        entity_id=source.id,
        as_of=as_of,
    )
    current_unfiltered = await service.list_for_entity(
        db_session,
        user_id=user.id,
        entity_type="project",
        entity_id=source.id,
    )

    assert {relationship.id for relationship in historical} == {
        created[0].id,
        created[1].id,
    }
    assert {relationship.id for relationship in current_unfiltered} == {
        relationship.id for relationship in created
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_for_entity_keeps_historical_results_user_scoped(
    db_session: AsyncSession,
) -> None:
    owner = await _create_user(db_session, "historical-owner")
    other_user = await _create_user(db_session, "historical-other-owner")
    source = await _create_project(db_session, user_id=owner.id, name="Owned Source")
    owned_target = await _create_project(db_session, user_id=owner.id, name="Owned Target")
    foreign_source = await _create_project(
        db_session,
        user_id=other_user.id,
        name="Foreign Source",
    )
    foreign_target = await _create_project(
        db_session,
        user_id=other_user.id,
        name="Foreign Target",
    )
    as_of = datetime(2026, 10, 15, tzinfo=UTC)
    service = RelationshipService()
    owned = await service.create_relationship(
        db_session,
        user_id=owner.id,
        source_type="project",
        source_id=source.id,
        relationship_type="related_to",
        target_type="project",
        target_id=owned_target.id,
        valid_from=datetime(2026, 10, 1, tzinfo=UTC),
        valid_until=datetime(2026, 11, 1, tzinfo=UTC),
    )
    await service.create_relationship(
        db_session,
        user_id=other_user.id,
        source_type="project",
        source_id=foreign_source.id,
        relationship_type="related_to",
        target_type="project",
        target_id=foreign_target.id,
        valid_from=datetime(2026, 10, 1, tzinfo=UTC),
        valid_until=datetime(2026, 11, 1, tzinfo=UTC),
    )

    results = await service.list_for_entity(
        db_session,
        user_id=owner.id,
        entity_type="project",
        entity_id=source.id,
        as_of=as_of,
    )

    assert [relationship.id for relationship in results] == [owned.id]
