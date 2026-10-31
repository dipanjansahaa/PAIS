from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.commitment import Commitment, CommitmentSource
from app.database.models.decision import Decision, DecisionSource
from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.knowledge_relationship import (
    KnowledgeRelationship,
    KnowledgeRelationshipSource,
)
from app.database.models.memory import Memory, MemorySource
from app.database.models.project import Project
from app.database.models.task import Task, TaskSource
from app.database.models.user import User
from app.relationships.graph_builder import KnowledgeGraphConstructionService


@pytest_asyncio.fixture
async def graph_user(db_session: AsyncSession):
    user = User(
        email=f"graph-builder-{uuid4()}@example.com",
        display_name="Graph Builder Integration User",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.mark.asyncio
async def test_construct_for_user_persists_explicit_edges_and_provenance(
    db_session: AsyncSession,
    graph_user: User,
):
    project = Project(
        user_id=graph_user.id,
        name="Graph Builder Project",
        description="Integration fixture",
        status="active",
    )
    db_session.add(project)
    await db_session.flush()

    document = Document(
        user_id=graph_user.id,
        project_id=project.id,
        title="Graph source",
        source_type="notes",
        content_hash=f"graph-{uuid4()}",
        raw_text="A source for explicit graph edges.",
    )
    db_session.add(document)
    await db_session.flush()

    chunk = DocumentChunk(
        document_id=document.id,
        chunk_index=0,
        content="A source for explicit graph edges.",
        embedding=[1.0] + [0.0] * 383,
    )
    db_session.add(chunk)
    await db_session.flush()

    commitment = Commitment(
        user_id=graph_user.id,
        project_id=project.id,
        description="Review the release plan",
        status="open",
    )
    decision = Decision(
        user_id=graph_user.id,
        project_id=project.id,
        title="Use staged rollout",
        description="Release to a small cohort first.",
        status="active",
    )
    old_memory = Memory(
        user_id=graph_user.id,
        memory_type="fact",
        content="The project uses a single-stage rollout.",
        status="superseded",
    )
    db_session.add_all([commitment, decision, old_memory])
    await db_session.flush()

    new_memory = Memory(
        user_id=graph_user.id,
        memory_type="fact",
        content="The project uses a staged rollout.",
        status="active",
        supersedes_id=old_memory.id,
    )
    task = Task(
        user_id=graph_user.id,
        project_id=project.id,
        commitment_id=commitment.id,
        description="Review the release plan",
        status="open",
    )
    db_session.add_all([new_memory, task])
    await db_session.flush()

    db_session.add_all(
        [
            TaskSource(task_id=task.id, chunk_id=chunk.id),
            CommitmentSource(commitment_id=commitment.id, chunk_id=chunk.id),
            DecisionSource(decision_id=decision.id, chunk_id=chunk.id),
            MemorySource(
                memory_id=new_memory.id,
                source_kind="document_chunk",
                document_id=document.id,
                chunk_id=chunk.id,
                evidence_text="The project uses a staged rollout.",
            ),
        ]
    )
    await db_session.flush()

    service = KnowledgeGraphConstructionService()
    first = await service.construct_for_user(db_session, user_id=graph_user.id)
    await db_session.flush()

    assert first.relationships_processed == 6
    assert first.provenance_links_processed == 6

    relationships = list(
        (
            await db_session.scalars(
                select(KnowledgeRelationship).where(
                    KnowledgeRelationship.user_id == graph_user.id
                )
            )
        ).all()
    )
    assert len(relationships) == 6
    edge_keys = {
        (
            edge.source_type,
            edge.source_id,
            edge.relationship_type,
            edge.target_type,
            edge.target_id,
        )
        for edge in relationships
    }
    assert (
        "document", document.id, "belongs_to", "project", project.id
    ) in edge_keys
    assert (
        "commitment", commitment.id, "fulfills", "task", task.id
    ) in edge_keys
    assert (
        "memory", new_memory.id, "supersedes", "memory", old_memory.id
    ) in edge_keys

    sources = list(
        (
            await db_session.scalars(
                select(KnowledgeRelationshipSource).where(
                    KnowledgeRelationshipSource.relationship_id.in_(
                        [edge.id for edge in relationships]
                    )
                )
            )
        ).all()
    )
    assert len(sources) == 6
    assert {source.chunk_id for source in sources} == {chunk.id}

    second = await service.construct_for_user(db_session, user_id=graph_user.id)
    await db_session.flush()
    assert second.relationships_processed == 6

    relationships_after_second_run = list(
        (
            await db_session.scalars(
                select(KnowledgeRelationship).where(
                    KnowledgeRelationship.user_id == graph_user.id
                )
            )
        ).all()
    )
    sources_after_second_run = list(
        (
            await db_session.scalars(
                select(KnowledgeRelationshipSource).where(
                    KnowledgeRelationshipSource.relationship_id.in_(
                        [edge.id for edge in relationships_after_second_run]
                    )
                )
            )
        ).all()
    )
    assert len(relationships_after_second_run) == 6
    assert len(sources_after_second_run) == 6
