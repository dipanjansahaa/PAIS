from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.database.models.knowledge_relationship import (
    KnowledgeRelationship,
    KnowledgeRelationshipSource,
)
from app.relationships.service import RelationshipService


def _session(*, scalar_values=(), scalar_lists=()):
    session = MagicMock()
    session.scalar = AsyncMock(side_effect=list(scalar_values))
    results = []
    for values in scalar_lists:
        result = MagicMock()
        result.all.return_value = list(values)
        results.append(result)
    session.scalars = AsyncMock(side_effect=results)
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_create_relationship_persists_valid_directed_edge() -> None:
    user_id, source_id, target_id = uuid4(), uuid4(), uuid4()
    persisted = KnowledgeRelationship(
        user_id=user_id,
        source_type="task",
        source_id=source_id,
        relationship_type="depends_on",
        target_type="task",
        target_id=target_id,
    )
    session = _session(scalar_values=[source_id, target_id, None, persisted])

    result = await RelationshipService().create_relationship(
        session,
        user_id=user_id,
        source_type="task",
        source_id=source_id,
        relationship_type="depends_on",
        target_type="task",
        target_id=target_id,
    )

    assert isinstance(result, KnowledgeRelationship)
    assert result.user_id == user_id
    assert result.source_type == "task"
    assert result.source_id == source_id
    assert result.relationship_type == "depends_on"
    assert result.target_type == "task"
    assert result.target_id == target_id
    assert result is persisted
    session.execute.assert_awaited_once()
    insert_statement = session.execute.call_args.args[0]
    assert "uq_knowledge_relationships_directed_edge" in str(insert_statement)
    session.flush.assert_not_awaited()
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_create_relationship_returns_existing_duplicate() -> None:
    source_id, target_id = uuid4(), uuid4()
    existing = KnowledgeRelationship(
        user_id=uuid4(),
        source_type="project",
        source_id=source_id,
        relationship_type="related_to",
        target_type="person",
        target_id=target_id,
    )
    session = _session(scalar_values=[source_id, target_id, existing])

    result = await RelationshipService().create_relationship(
        session,
        user_id=existing.user_id,
        source_type="project",
        source_id=source_id,
        relationship_type="related_to",
        target_type="person",
        target_id=target_id,
    )

    assert result is existing
    session.add.assert_not_called()
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_relationship_rejects_unsupported_entity_type() -> None:
    session = _session()

    with pytest.raises(ValueError, match="Unsupported knowledge entity type"):
        await RelationshipService().create_relationship(
            session,
            user_id=uuid4(),
            source_type="unknown",
            source_id=uuid4(),
            relationship_type="related_to",
            target_type="person",
            target_id=uuid4(),
        )

    session.scalar.assert_not_awaited()
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_create_relationship_rejects_unsupported_relationship_type() -> None:
    session = _session()

    with pytest.raises(
        ValueError,
        match="Unsupported knowledge relationship type",
    ):
        await RelationshipService().create_relationship(
            session,
            user_id=uuid4(),
            source_type="project",
            source_id=uuid4(),
            relationship_type="invented_relation",
            target_type="person",
            target_id=uuid4(),
        )

    session.scalar.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_relationship_rejects_self_reference() -> None:
    entity_id = uuid4()
    session = _session()

    with pytest.raises(ValueError, match="cannot reference itself"):
        await RelationshipService().create_relationship(
            session,
            user_id=uuid4(),
            source_type="task",
            source_id=entity_id,
            relationship_type="related_to",
            target_type="task",
            target_id=entity_id,
        )

    session.scalar.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_relationship_rejects_missing_or_foreign_endpoint() -> None:
    session = _session(scalar_values=[None])

    with pytest.raises(
        ValueError,
        match="Project does not exist or does not belong to the user",
    ):
        await RelationshipService().create_relationship(
            session,
            user_id=uuid4(),
            source_type="project",
            source_id=uuid4(),
            relationship_type="related_to",
            target_type="person",
            target_id=uuid4(),
        )

    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_create_relationship_rejects_non_uuid_endpoint_id() -> None:
    session = _session()

    with pytest.raises(ValueError, match="source_id must be a UUID"):
        await RelationshipService().create_relationship(
            session,
            user_id=uuid4(),
            source_type="project",
            source_id="not-a-uuid",  # type: ignore[arg-type]
            relationship_type="related_to",
            target_type="person",
            target_id=uuid4(),
        )

    session.scalar.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_relationship_is_user_scoped() -> None:
    relationship_id = uuid4()
    expected = KnowledgeRelationship(
        user_id=uuid4(),
        source_type="project",
        source_id=uuid4(),
        relationship_type="related_to",
        target_type="person",
        target_id=uuid4(),
    )
    session = _session(scalar_values=[expected])

    result = await RelationshipService().get_relationship(
        session,
        user_id=expected.user_id,
        relationship_id=relationship_id,
    )

    assert result is expected
    query = session.scalar.call_args.args[0]
    assert "knowledge_relationships.user_id" in str(query)


@pytest.mark.asyncio
async def test_list_for_entity_validates_limit() -> None:
    session = _session()

    with pytest.raises(ValueError, match="limit must be between 1 and 100"):
        await RelationshipService().list_for_entity(
            session,
            user_id=uuid4(),
            entity_type="project",
            entity_id=uuid4(),
            limit=101,
        )

    session.scalar.assert_not_awaited()
    session.scalars.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_sources_deduplicates_chunk_ids_and_is_idempotent() -> None:
    user_id, relationship_id = uuid4(), uuid4()
    chunk_a, chunk_b = uuid4(), uuid4()
    relationship = KnowledgeRelationship(
        user_id=user_id,
        source_type="project",
        source_id=uuid4(),
        relationship_type="references",
        target_type="document",
        target_id=uuid4(),
    )
    source_a = KnowledgeRelationshipSource(
        relationship_id=relationship_id,
        chunk_id=chunk_a,
    )
    existing = KnowledgeRelationshipSource(
        relationship_id=relationship_id,
        chunk_id=chunk_b,
    )
    session = _session(
        scalar_values=[relationship],
        scalar_lists=[[chunk_a, chunk_b], [source_a, existing]],
    )

    result = await RelationshipService().add_sources(
        session,
        user_id=user_id,
        relationship_id=relationship_id,
        chunk_ids=[chunk_a, chunk_b, chunk_a],
    )

    assert [source.chunk_id for source in result] == [chunk_a, chunk_b]
    assert result == [source_a, existing]
    session.execute.assert_awaited_once()
    insert_statement = session.execute.call_args.args[0]
    assert "ON CONFLICT (relationship_id, chunk_id) DO NOTHING" in str(insert_statement)
    session.add_all.assert_not_called()
    session.flush.assert_not_awaited()
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_add_sources_rejects_relationship_not_owned_by_user() -> None:
    session = _session(scalar_values=[None])

    with pytest.raises(ValueError, match="Relationship does not belong to the user"):
        await RelationshipService().add_sources(
            session,
            user_id=uuid4(),
            relationship_id=uuid4(),
            chunk_ids=[uuid4()],
        )

    session.scalars.assert_not_awaited()
    session.add_all.assert_not_called()


@pytest.mark.asyncio
async def test_add_sources_rejects_foreign_chunk() -> None:
    session = _session(
        scalar_values=[MagicMock(spec=KnowledgeRelationship)],
        scalar_lists=[[]],
    )

    with pytest.raises(
        ValueError,
        match="One or more source chunks do not belong to the user",
    ):
        await RelationshipService().add_sources(
            session,
            user_id=uuid4(),
            relationship_id=uuid4(),
            chunk_ids=[uuid4()],
        )

    session.add_all.assert_not_called()


@pytest.mark.asyncio
async def test_add_sources_rejects_empty_list() -> None:
    session = _session()

    with pytest.raises(ValueError, match="At least one source chunk is required"):
        await RelationshipService().add_sources(
            session,
            user_id=uuid4(),
            relationship_id=uuid4(),
            chunk_ids=[],
        )

    session.scalar.assert_not_awaited()
