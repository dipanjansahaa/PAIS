from __future__ import annotations

from uuid import uuid4

import pytest
from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.knowledge_relationship import (
    KnowledgeRelationship,
    KnowledgeRelationshipSource,
)
from app.database.models.person import Person
from app.database.models.task import Task, TaskSource
from app.database.models.user import User
from app.relationships.graph_builder import KnowledgeGraphConstructionService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_exact_owner_reference_creates_assigned_to_edge_with_provenance(
    db_session: AsyncSession,
):
    user = User(
        email=f"entity-linking-{uuid4()}@example.com",
        display_name="Entity Linking Integration User",
    )
    db_session.add(user)
    await db_session.flush()

    person = Person(
        user_id=user.id,
        name="Ada Lovelace",
        email="ada@example.com",
    )
    document = Document(
        user_id=user.id,
        title="Owner evidence",
        source_type="notes",
        content_hash=f"entity-linking-{uuid4()}",
        raw_text="Ada owns the review task.",
    )
    db_session.add_all([person, document])
    await db_session.flush()

    chunk = DocumentChunk(
        document_id=document.id,
        chunk_index=0,
        content="Ada owns the review task.",
        embedding=[1.0] + [0.0] * 383,
    )
    db_session.add(chunk)
    await db_session.flush()

    task = Task(
        user_id=user.id,
        description="Review the release plan",
        owner=" ADA@EXAMPLE.COM ",
        status="open",
    )
    db_session.add(task)
    await db_session.flush()
    db_session.add(TaskSource(task_id=task.id, chunk_id=chunk.id))
    await db_session.flush()

    result = await KnowledgeGraphConstructionService().construct_for_user(
        db_session, user_id=user.id
    )
    await db_session.flush()

    assert result.person_links_matched == 1
    assert result.person_links_ambiguous == 0
    assert result.person_links_unmatched == 0
    edge = await db_session.scalar(
        select(KnowledgeRelationship).where(
            KnowledgeRelationship.user_id == user.id,
            KnowledgeRelationship.source_type == "task",
            KnowledgeRelationship.source_id == task.id,
            KnowledgeRelationship.relationship_type == "assigned_to",
            KnowledgeRelationship.target_type == "person",
            KnowledgeRelationship.target_id == person.id,
        )
    )
    assert edge is not None
    source = await db_session.scalar(
        select(KnowledgeRelationshipSource).where(
            KnowledgeRelationshipSource.relationship_id == edge.id,
            KnowledgeRelationshipSource.chunk_id == chunk.id,
        )
    )
    assert source is not None


@pytest.mark.asyncio
async def test_ambiguous_owner_reference_does_not_create_edge(
    db_session: AsyncSession,
):
    user = User(
        email=f"entity-ambiguous-{uuid4()}@example.com",
        display_name="Ambiguous Entity Linking User",
    )
    db_session.add(user)
    await db_session.flush()

    db_session.add_all(
        [
            Person(user_id=user.id, name="Alex Kim", email="alex.one@example.com"),
            Person(user_id=user.id, name="Alex Kim", email="alex.two@example.com"),
        ]
    )
    await db_session.flush()
    task = Task(user_id=user.id, description="Review the plan", owner="Alex Kim")
    db_session.add(task)
    await db_session.flush()

    result = await KnowledgeGraphConstructionService().construct_for_user(
        db_session, user_id=user.id
    )

    assert result.person_links_matched == 0
    assert result.person_links_ambiguous == 1
    assert result.person_links_unmatched == 0
    edge = await db_session.scalar(
        select(KnowledgeRelationship).where(
            KnowledgeRelationship.user_id == user.id,
            KnowledgeRelationship.source_type == "task",
            KnowledgeRelationship.source_id == task.id,
            KnowledgeRelationship.relationship_type == "assigned_to",
        )
    )
    assert edge is None
