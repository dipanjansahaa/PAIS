"""Integration tests for commitment persistence."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.commitments.service import CommitmentService
from app.database.models.commitment import Commitment, CommitmentSource
from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.user import User
from app.intelligence.models import (
    CommitmentCandidate,
    IntelligenceSource,
)


@pytest.mark.asyncio
async def test_create_commitment_from_candidate_persists_commitment_and_provenance(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"commitment-{uuid4()}@example.com",
        display_name="Commitment Integration User",
    )

    db_session.add(user)
    await db_session.flush()

    document = Document(
        user_id=user.id,
        title="Commitment Source Document",
        source_type="test",
        file_name="commitments.txt",
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

    candidate = CommitmentCandidate(
        description="Review the deployment",
        owner="Dipanjan",
        sources=[
            IntelligenceSource(chunk_id=chunk.id),
        ],
    )

    service = CommitmentService()

    commitment = await service.create_from_candidate(
        db_session,
        user_id=user.id,
        candidate=candidate,
    )

    assert commitment.id is not None
    assert commitment.user_id == user.id
    assert commitment.description == candidate.description
    assert commitment.owner == candidate.owner

    source = await db_session.scalar(
        select(CommitmentSource).where(
            CommitmentSource.commitment_id == commitment.id,
            CommitmentSource.chunk_id == chunk.id,
        )
    )

    assert source is not None

    persisted_commitment = await db_session.scalar(
        select(Commitment).where(
            Commitment.id == commitment.id,
            Commitment.user_id == user.id,
        )
    )

    assert persisted_commitment is not None
    assert persisted_commitment.description == (
        "Review the deployment"
    )


@pytest.mark.asyncio
async def test_create_commitment_with_multiple_sources(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"commitment-multi-{uuid4()}@example.com",
        display_name="Commitment Multi Source User",
    )

    db_session.add(user)
    await db_session.flush()

    document = Document(
        user_id=user.id,
        title="Multiple Commitment Sources",
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

    candidate = CommitmentCandidate(
        description="Combine the findings",
        sources=[
            IntelligenceSource(chunk_id=chunks[0].id),
            IntelligenceSource(chunk_id=chunks[1].id),
        ],
    )

    service = CommitmentService()

    commitment = await service.create_from_candidate(
        db_session,
        user_id=user.id,
        candidate=candidate,
    )

    sources = (
        await db_session.scalars(
            select(CommitmentSource).where(
                CommitmentSource.commitment_id == commitment.id,
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
async def test_commitment_cannot_use_foreign_source_chunk(
    db_session: AsyncSession,
) -> None:
    owner = User(
        email=f"commitment-owner-{uuid4()}@example.com",
        display_name="Commitment Owner",
    )

    other_user = User(
        email=f"commitment-other-{uuid4()}@example.com",
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
        raw_text="Private commitment source.",
    )

    db_session.add(document)
    await db_session.flush()

    chunk = DocumentChunk(
        document_id=document.id,
        chunk_index=0,
        content="Private commitment source.",
        embedding=[1.0] + [0.0] * 383,
    )

    db_session.add(chunk)
    await db_session.flush()

    candidate = CommitmentCandidate(
        description="Access private source",
        sources=[
            IntelligenceSource(chunk_id=chunk.id),
        ],
    )

    service = CommitmentService()

    with pytest.raises(
        ValueError,
        match="source chunks do not belong to the user",
    ):
        await service.create_from_candidate(
            db_session,
            user_id=owner.id,
            candidate=candidate,
        )