from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.intelligence.models import IntelligenceSource, TaskCandidate
from app.tasks.service import TaskService


@pytest.mark.asyncio
async def test_create_from_candidate_persists_task_and_sources():
    user_id = uuid4()
    chunk_id_1 = uuid4()
    chunk_id_2 = uuid4()

    candidate = TaskCandidate(
        description="Review deployment",
        owner="Dipanjan",
        due_at=datetime(
            2026,
            10,
            1,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        priority="high",
        sources=[
            IntelligenceSource(chunk_id=chunk_id_1),
            IntelligenceSource(chunk_id=chunk_id_2),
        ],
    )

    session = MagicMock()

    session.scalar = AsyncMock()
    session.scalars = AsyncMock()
    session.flush = AsyncMock()

    project_result = None
    commitment_result = None

    session.scalar.side_effect = [
        project_result,
        commitment_result,
    ]

    source_result = MagicMock()
    source_result.all.return_value = [
        chunk_id_1,
        chunk_id_2,
    ]
    session.scalars.return_value = source_result

    service = TaskService()

    task = await service.create_from_candidate(
        session,
        user_id=user_id,
        candidate=candidate,
    )

    assert task.user_id == user_id
    assert task.description == "Review deployment"
    assert task.owner == "Dipanjan"
    assert task.priority == "high"
    assert task.due_at == candidate.due_at

    assert session.add.call_count == 1
    assert session.add_all.call_count == 1
    assert session.flush.call_count == 2


@pytest.mark.asyncio
async def test_create_from_candidate_deduplicates_source_chunks():
    user_id = uuid4()
    chunk_id = uuid4()

    candidate = TaskCandidate(
        description="Review deployment",
        sources=[
            IntelligenceSource(chunk_id=chunk_id),
            IntelligenceSource(chunk_id=chunk_id),
        ],
    )

    session = MagicMock()

    session.scalar = AsyncMock()
    session.scalars = AsyncMock()
    session.flush = AsyncMock()

    source_result = MagicMock()
    source_result.all.return_value = [chunk_id]
    session.scalars.return_value = source_result

    service = TaskService()

    await service.create_from_candidate(
        session,
        user_id=user_id,
        candidate=candidate,
    )

    sources = session.add_all.call_args.args[0]

    assert len(sources) == 1
    assert sources[0].chunk_id == chunk_id


@pytest.mark.asyncio
async def test_create_from_candidate_rejects_invalid_project():
    user_id = uuid4()
    project_id = uuid4()
    chunk_id = uuid4()

    candidate = TaskCandidate(
        description="Review deployment",
        sources=[
            IntelligenceSource(chunk_id=chunk_id),
        ],
    )

    session = AsyncMock()
    session.scalar.return_value = None

    service = TaskService()

    with pytest.raises(
        ValueError,
        match="Project does not belong to the user",
    ):
        await service.create_from_candidate(
            session,
            user_id=user_id,
            candidate=candidate,
            project_id=project_id,
        )


@pytest.mark.asyncio
async def test_create_from_candidate_rejects_invalid_commitment():
    user_id = uuid4()
    commitment_id = uuid4()
    chunk_id = uuid4()

    candidate = TaskCandidate(
        description="Review deployment",
        sources=[
            IntelligenceSource(chunk_id=chunk_id),
        ],
    )

    session = AsyncMock()

    session.scalar.side_effect = [
        None,
        None,
    ]

    service = TaskService()

    with pytest.raises(
        ValueError,
        match="Commitment does not belong to the user",
    ):
        await service.create_from_candidate(
            session,
            user_id=user_id,
            candidate=candidate,
            commitment_id=commitment_id,
        )


@pytest.mark.asyncio
async def test_create_from_candidate_rejects_foreign_source_chunk():
    user_id = uuid4()
    chunk_id = uuid4()

    candidate = TaskCandidate(
        description="Review deployment",
        sources=[
            IntelligenceSource(chunk_id=chunk_id),
        ],
    )

    session = AsyncMock()

    source_result = MagicMock()
    source_result.all.return_value = []
    session.scalars.return_value = source_result

    service = TaskService()

    with pytest.raises(
        ValueError,
        match="source chunks do not belong to the user",
    ):
        await service.create_from_candidate(
            session,
            user_id=user_id,
            candidate=candidate,
        )