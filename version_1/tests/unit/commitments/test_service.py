from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.commitments.service import CommitmentService
from app.intelligence.models import CommitmentCandidate, IntelligenceSource


@pytest.mark.asyncio
async def test_create_from_candidate_persists_commitment_and_sources():
    user_id = uuid4()
    chunk_id_1 = uuid4()
    chunk_id_2 = uuid4()

    deadline = datetime(
        2026,
        10,
        2,
        12,
        0,
        tzinfo=timezone.utc,
    )

    candidate = CommitmentCandidate(
        description="Review the deployment",
        owner="Dipanjan",
        deadline_at=deadline,
        sources=[
            IntelligenceSource(chunk_id=chunk_id_1),
            IntelligenceSource(chunk_id=chunk_id_2),
        ],
    )

    session = MagicMock()

    session.scalar = AsyncMock()
    session.scalars = AsyncMock()
    session.flush = AsyncMock()

    source_result = MagicMock()
    source_result.all.return_value = [
        chunk_id_1,
        chunk_id_2,
    ]
    session.scalars.return_value = source_result

    service = CommitmentService()

    commitment = await service.create_from_candidate(
        session,
        user_id=user_id,
        candidate=candidate,
    )

    assert commitment.user_id == user_id
    assert commitment.description == "Review the deployment"
    assert commitment.owner == "Dipanjan"
    assert commitment.deadline_at == deadline

    assert session.add.call_count == 1
    assert session.add_all.call_count == 1
    assert session.flush.call_count == 2


@pytest.mark.asyncio
async def test_create_from_candidate_deduplicates_source_chunks():
    user_id = uuid4()
    chunk_id = uuid4()

    candidate = CommitmentCandidate(
        description="Review the deployment",
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

    service = CommitmentService()

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

    candidate = CommitmentCandidate(
        description="Review the deployment",
        sources=[
            IntelligenceSource(chunk_id=chunk_id),
        ],
    )

    session = AsyncMock()
    session.scalar.return_value = None

    service = CommitmentService()

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
async def test_create_from_candidate_rejects_foreign_source_chunk():
    user_id = uuid4()
    chunk_id = uuid4()

    candidate = CommitmentCandidate(
        description="Review the deployment",
        sources=[
            IntelligenceSource(chunk_id=chunk_id),
        ],
    )

    session = AsyncMock()

    source_result = MagicMock()
    source_result.all.return_value = []
    session.scalars.return_value = source_result

    service = CommitmentService()

    with pytest.raises(
        ValueError,
        match="source chunks do not belong to the user",
    ):
        await service.create_from_candidate(
            session,
            user_id=user_id,
            candidate=candidate,
        )