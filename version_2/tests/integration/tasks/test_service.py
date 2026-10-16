"""Integration tests for task persistence."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.task import Task, TaskSource
from app.database.models.user import User
from app.intelligence.models import IntelligenceSource, TaskCandidate
from app.tasks.service import TaskService


@pytest.mark.asyncio
async def test_create_task_from_candidate_persists_task_and_provenance(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"task-{uuid4()}@example.com",
        display_name="Task Integration User",
    )

    db_session.add(user)
    await db_session.flush()

    document = Document(
        user_id=user.id,
        title="Task Source Document",
        source_type="test",
        file_name="tasks.txt",
        mime_type="text/plain",
        content_hash=uuid4().hex,
        raw_text="Review deployment before Friday.",
    )

    db_session.add(document)
    await db_session.flush()

    chunk = DocumentChunk(
        document_id=document.id,
        chunk_index=0,
        content="Review deployment before Friday.",
        embedding=[1.0] + [0.0] * 383,
    )

    db_session.add(chunk)
    await db_session.flush()

    candidate = TaskCandidate(
        description="Review deployment before Friday",
        owner="Dipanjan",
        priority="high",
        sources=[
            IntelligenceSource(chunk_id=chunk.id),
        ],
    )

    service = TaskService()

    task = await service.create_from_candidate(
        db_session,
        user_id=user.id,
        candidate=candidate,
    )

    assert task.id is not None
    assert task.user_id == user.id
    assert task.description == candidate.description
    assert task.owner == candidate.owner
    assert task.priority == candidate.priority

    source = await db_session.scalar(
        select(TaskSource).where(
            TaskSource.task_id == task.id,
            TaskSource.chunk_id == chunk.id,
        )
    )

    assert source is not None

    persisted_task = await db_session.scalar(
        select(Task).where(
            Task.id == task.id,
            Task.user_id == user.id,
        )
    )

    assert persisted_task is not None
    assert persisted_task.description == (
        "Review deployment before Friday"
    )


@pytest.mark.asyncio
async def test_create_task_with_multiple_sources(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"task-multi-{uuid4()}@example.com",
        display_name="Task Multi Source User",
    )

    db_session.add(user)
    await db_session.flush()

    document = Document(
        user_id=user.id,
        title="Multiple Task Sources",
        source_type="test",
        file_name="multiple.txt",
        mime_type="text/plain",
        content_hash=uuid4().hex,
        raw_text="Source one. Source two.",
    )

    db_session.add(document)
    await db_session.flush()

    chunks = [
        DocumentChunk(
            document_id=document.id,
            chunk_index=0,
            content="Source one.",
            embedding=[1.0] + [0.0] * 383,
        ),
        DocumentChunk(
            document_id=document.id,
            chunk_index=1,
            content="Source two.",
            embedding=[0.0, 1.0] + [0.0] * 382,
        ),
    ]

    db_session.add_all(chunks)
    await db_session.flush()

    candidate = TaskCandidate(
        description="Combine the findings",
        sources=[
            IntelligenceSource(chunk_id=chunks[0].id),
            IntelligenceSource(chunk_id=chunks[1].id),
        ],
    )

    service = TaskService()

    task = await service.create_from_candidate(
        db_session,
        user_id=user.id,
        candidate=candidate,
    )

    sources = (
        await db_session.scalars(
            select(TaskSource).where(
                TaskSource.task_id == task.id,
            )
        )
    ).all()

    assert len(sources) == 2
    assert {
        source.chunk_id
        for source in sources
    } == {
        chunks[0].id,
        chunks[1].id,
    }


@pytest.mark.asyncio
async def test_task_cannot_use_foreign_source_chunk(
    db_session: AsyncSession,
) -> None:
    owner = User(
        email=f"task-owner-{uuid4()}@example.com",
        display_name="Task Owner",
    )

    other_user = User(
        email=f"task-other-{uuid4()}@example.com",
        display_name="Other User",
    )

    db_session.add_all([owner, other_user])
    await db_session.flush()

    document = Document(
        user_id=other_user.id,
        title="Other User Document",
        source_type="test",
        file_name="other.txt",
        mime_type="text/plain",
        content_hash=uuid4().hex,
        raw_text="Private source.",
    )

    db_session.add(document)
    await db_session.flush()

    chunk = DocumentChunk(
        document_id=document.id,
        chunk_index=0,
        content="Private source.",
        embedding=[1.0] + [0.0] * 383,
    )

    db_session.add(chunk)
    await db_session.flush()

    candidate = TaskCandidate(
        description="Access private source",
        sources=[
            IntelligenceSource(chunk_id=chunk.id),
        ],
    )

    service = TaskService()

    with pytest.raises(
        ValueError,
        match="source chunks do not belong to the user",
    ):
        await service.create_from_candidate(
            db_session,
            user_id=owner.id,
            candidate=candidate,
        )


@pytest.mark.asyncio
async def test_task_can_be_linked_to_commitment(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"task-commitment-{uuid4()}@example.com",
        display_name="Task Commitment User",
    )

    db_session.add(user)
    await db_session.flush()

    document = Document(
        user_id=user.id,
        title="Commitment Source",
        source_type="test",
        file_name="commitment.txt",
        mime_type="text/plain",
        content_hash=uuid4().hex,
        raw_text="I will review the deployment tomorrow.",
    )

    db_session.add(document)
    await db_session.flush()

    chunk = DocumentChunk(
        document_id=document.id,
        chunk_index=0,
        content="I will review the deployment tomorrow.",
        embedding=[1.0] + [0.0] * 383,
    )

    db_session.add(chunk)
    await db_session.flush()

    from app.commitments.service import CommitmentService
    from app.intelligence.models import CommitmentCandidate

    commitment = await CommitmentService().create_from_candidate(
        db_session,
        user_id=user.id,
        candidate=CommitmentCandidate(
            description="Review the deployment",
            sources=[
                IntelligenceSource(chunk_id=chunk.id),
            ],
        ),
    )

    task = await TaskService().create_from_candidate(
        db_session,
        user_id=user.id,
        candidate=TaskCandidate(
            description="Review deployment logs",
            sources=[
                IntelligenceSource(chunk_id=chunk.id),
            ],
        ),
        commitment_id=commitment.id,
    )

    assert task.commitment_id == commitment.id