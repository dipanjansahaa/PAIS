"""Integration tests for relationship-aware query context construction."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.knowledge_relationship import KnowledgeRelationshipSource
from app.database.models.project import Project
from app.database.models.user import User
from app.query.relationship_context import RelationshipContextBuilder
from app.relationships.service import RelationshipService


async def _create_user(session: AsyncSession, label: str) -> User:
    user = User(
        email=f"query-relationship-{label}-{uuid4()}@example.com",
        display_name=f"Query Relationship {label.title()} User",
    )
    session.add(user)
    await session.flush()
    return user


@pytest.mark.integration
@pytest.mark.asyncio
async def test_relationship_context_includes_labels_and_provenance(
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, "owner")
    source = Project(user_id=user.id, name="PAIS")
    target = Project(user_id=user.id, name="Retrieval milestone")
    document = Document(
        user_id=user.id,
        title="Roadmap evidence",
        source_type="test",
        content_hash=uuid4().hex,
        raw_text="PAIS retrieval milestone depends on relationship-aware context.",
    )
    db_session.add_all([source, target, document])
    await db_session.flush()
    chunk = DocumentChunk(
        document_id=document.id,
        chunk_index=0,
        content="PAIS retrieval milestone depends on relationship-aware context.",
    )
    db_session.add(chunk)
    await db_session.flush()

    relationship_service = RelationshipService()
    relationship = await relationship_service.create_relationship(
        db_session,
        user_id=user.id,
        source_type="project",
        source_id=source.id,
        relationship_type="depends_on",
        target_type="project",
        target_id=target.id,
    )
    await relationship_service.add_sources(
        db_session,
        user_id=user.id,
        relationship_id=relationship.id,
        chunk_ids=[chunk.id],
    )

    context = await RelationshipContextBuilder().build(
        db_session,
        user_id=user.id,
        entity_type="project",
        entity_id=source.id,
    )

    assert len(context.relationships) == 1
    result = context.relationships[0]
    assert result.source_label == "PAIS"
    assert result.target_label == "Retrieval milestone"
    assert result.relationship_type == "depends_on"
    assert len(result.sources) == 1
    assert result.sources[0].document_title == "Roadmap evidence"
    assert "relationship-aware context" in result.sources[0].content
    assert "[R1-C1]" in context.text

    persisted_sources = await db_session.scalars(
        select(KnowledgeRelationshipSource).where(
            KnowledgeRelationshipSource.relationship_id == relationship.id,
        )
    )
    assert len(persisted_sources.all()) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_relationship_context_is_scoped_to_user(
    db_session: AsyncSession,
) -> None:
    owner = await _create_user(db_session, "owner")
    other_user = await _create_user(db_session, "other")
    owned_project = Project(user_id=owner.id, name="Owned project")
    foreign_project = Project(user_id=other_user.id, name="Foreign project")
    foreign_target = Project(user_id=other_user.id, name="Foreign target")
    db_session.add_all([owned_project, foreign_project, foreign_target])
    await db_session.flush()

    # Create a valid relationship for the other user; the owner must not be
    # able to use the foreign entity as a seed or receive its graph context.
    await RelationshipService().create_relationship(
        db_session,
        user_id=other_user.id,
        source_type="project",
        source_id=foreign_project.id,
        relationship_type="related_to",
        target_type="project",
        target_id=foreign_target.id,
    )

    builder = RelationshipContextBuilder()
    own_context = await builder.build(
        db_session,
        user_id=owner.id,
        entity_type="project",
        entity_id=owned_project.id,
    )
    assert own_context.relationships == ()

    with pytest.raises(ValueError, match="does not exist or does not belong"):
        await builder.build(
            db_session,
            user_id=owner.id,
            entity_type="project",
            entity_id=foreign_project.id,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_current_relationship_context_excludes_expired_edges(
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, "validity")
    source = Project(user_id=user.id, name="Current project")
    current_target = Project(user_id=user.id, name="Current dependency")
    expired_target = Project(user_id=user.id, name="Old dependency")
    db_session.add_all([source, current_target, expired_target])
    await db_session.flush()

    service = RelationshipService()
    await service.create_relationship(
        db_session,
        user_id=user.id,
        source_type="project",
        source_id=source.id,
        relationship_type="depends_on",
        target_type="project",
        target_id=current_target.id,
    )
    now = datetime.now(UTC)
    await service.create_relationship(
        db_session,
        user_id=user.id,
        source_type="project",
        source_id=source.id,
        relationship_type="related_to",
        target_type="project",
        target_id=expired_target.id,
        valid_from=now - timedelta(days=3),
        valid_until=now - timedelta(days=1),
    )

    context = await RelationshipContextBuilder().build(
        db_session,
        user_id=user.id,
        entity_type="project",
        entity_id=source.id,
    )

    assert [relationship.target_label for relationship in context.relationships] == [
        "Current dependency"
    ]
