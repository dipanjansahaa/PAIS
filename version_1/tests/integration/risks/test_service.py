from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.risk import Risk, RiskSource
from app.database.models.user import User
from app.intelligence.models import IntelligenceSource, RiskCandidate
from app.risks.service import RiskService


async def _create_source_chunks(
    db_session: AsyncSession,
    *,
    user_id,
    count: int = 1,
) -> list[DocumentChunk]:
    document = Document(
        user_id=user_id,
        title="Risk Source Document",
        source_type="test",
        file_name="risks.txt",
        mime_type="text/plain",
        content_hash=uuid4().hex,
        raw_text="Risk source material.",
    )

    db_session.add(document)
    await db_session.flush()

    chunks = [
        DocumentChunk(
            document_id=document.id,
            chunk_index=index,
            content=f"Risk source {index}.",
            embedding=[1.0] + [0.0] * 383,
        )
        for index in range(count)
    ]

    db_session.add_all(chunks)
    await db_session.flush()

    return chunks


def _candidate(
    *chunk_ids,
    title: str = "Deployment delay",
    description: str | None = "Deployment may be delayed.",
    severity: str | None = "high",
) -> RiskCandidate:
    return RiskCandidate(
        title=title,
        description=description,
        severity=severity,
        sources=[
            IntelligenceSource(chunk_id=chunk_id)
            for chunk_id in chunk_ids
        ],
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_risk_from_candidate_persists_risk_and_provenance(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"risk-{uuid4()}@example.com",
        display_name="Risk Integration User",
    )

    db_session.add(user)
    await db_session.flush()

    chunks = await _create_source_chunks(
        db_session,
        user_id=user.id,
    )

    risk = await RiskService().create_from_candidate(
        db_session,
        user_id=user.id,
        candidate=_candidate(chunks[0].id),
    )

    assert risk.id is not None
    assert risk.user_id == user.id
    assert risk.title == "Deployment delay"
    assert risk.description == "Deployment may be delayed."
    assert risk.severity == "high"

    stored_risk = await db_session.scalar(
        select(Risk).where(
            Risk.id == risk.id,
        )
    )

    assert stored_risk is not None
    assert stored_risk.user_id == user.id

    stored_source = await db_session.scalar(
        select(RiskSource).where(
            RiskSource.risk_id == risk.id,
            RiskSource.chunk_id == chunks[0].id,
        )
    )

    assert stored_source is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_risk_with_multiple_sources(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"risk-multi-{uuid4()}@example.com",
        display_name="Risk Multi Source User",
    )

    db_session.add(user)
    await db_session.flush()

    chunks = await _create_source_chunks(
        db_session,
        user_id=user.id,
        count=3,
    )

    risk = await RiskService().create_from_candidate(
        db_session,
        user_id=user.id,
        candidate=_candidate(
            chunks[0].id,
            chunks[1].id,
            chunks[2].id,
        ),
    )

    result = await db_session.scalars(
        select(RiskSource).where(
            RiskSource.risk_id == risk.id,
        )
    )

    sources = result.all()

    assert len(sources) == 3
    assert {source.chunk_id for source in sources} == {
        chunks[0].id,
        chunks[1].id,
        chunks[2].id,
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_risk_deduplicates_sources(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"risk-dedupe-{uuid4()}@example.com",
        display_name="Risk Dedupe User",
    )

    db_session.add(user)
    await db_session.flush()

    chunks = await _create_source_chunks(
        db_session,
        user_id=user.id,
    )

    risk = await RiskService().create_from_candidate(
        db_session,
        user_id=user.id,
        candidate=_candidate(
            chunks[0].id,
            chunks[0].id,
        ),
    )

    result = await db_session.scalars(
        select(RiskSource).where(
            RiskSource.risk_id == risk.id,
        )
    )

    sources = result.all()

    assert len(sources) == 1
    assert sources[0].chunk_id == chunks[0].id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_risk_cannot_use_foreign_source_chunk(
    db_session: AsyncSession,
) -> None:
    owner = User(
        email=f"risk-owner-{uuid4()}@example.com",
        display_name="Risk Owner",
    )

    foreign_user = User(
        email=f"risk-foreign-{uuid4()}@example.com",
        display_name="Foreign User",
    )

    db_session.add_all([owner, foreign_user])
    await db_session.flush()

    foreign_chunks = await _create_source_chunks(
        db_session,
        user_id=foreign_user.id,
    )

    with pytest.raises(
        ValueError,
        match="One or more source chunks do not belong to the user.",
    ):
        await RiskService().create_from_candidate(
            db_session,
            user_id=owner.id,
            candidate=_candidate(
                foreign_chunks[0].id,
            ),
        )

    stored_risk = await db_session.scalar(
        select(Risk).where(
            Risk.user_id == owner.id,
        )
    )

    assert stored_risk is None