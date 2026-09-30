from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.decision import Decision, DecisionSource
from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.project import Project
from app.database.models.user import User
from app.decisions.service import DecisionService
from app.intelligence.models import DecisionCandidate, IntelligenceSource


async def _create_source_chunks(
    db_session: AsyncSession,
    *,
    user_id,
    count: int = 1,
) -> list[DocumentChunk]:
    document = Document(
        user_id=user_id,
        title="Decision Source Document",
        source_type="test",
        file_name="decisions.txt",
        mime_type="text/plain",
        content_hash=uuid4().hex,
        raw_text="Decision source material.",
    )

    db_session.add(document)
    await db_session.flush()

    chunks = [
        DocumentChunk(
            document_id=document.id,
            chunk_index=index,
            content=f"Decision source {index}.",
            embedding=[1.0] + [0.0] * 383,
        )
        for index in range(count)
    ]

    db_session.add_all(chunks)
    await db_session.flush()

    return chunks


def _candidate(*chunk_ids) -> DecisionCandidate:
    return DecisionCandidate(
        title="Database choice",
        description="Use PostgreSQL for the persistence layer.",
        decision_date=datetime(
            2026,
            10,
            1,
            tzinfo=timezone.utc,
        ),
        sources=[
            IntelligenceSource(chunk_id=chunk_id)
            for chunk_id in chunk_ids
        ],
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_decision_from_candidate_persists_decision_and_provenance(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"decision-{uuid4()}@example.com",
        display_name="Decision Integration User",
    )

    db_session.add(user)
    await db_session.flush()

    chunks = await _create_source_chunks(
        db_session,
        user_id=user.id,
    )

    decision = await DecisionService().create_from_candidate(
        db_session,
        user_id=user.id,
        candidate=_candidate(chunks[0].id),
    )

    assert decision.id is not None
    assert decision.user_id == user.id
    assert decision.project_id is None
    assert decision.title == "Database choice"
    assert decision.description == (
        "Use PostgreSQL for the persistence layer."
    )
    assert decision.decision_date is not None
    assert decision.status == "active"

    stored_decision = await db_session.scalar(
        select(Decision).where(
            Decision.id == decision.id,
        )
    )

    assert stored_decision is not None
    assert stored_decision.user_id == user.id

    stored_source = await db_session.scalar(
        select(DecisionSource).where(
            DecisionSource.decision_id == decision.id,
            DecisionSource.chunk_id == chunks[0].id,
        )
    )

    assert stored_source is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_decision_with_multiple_sources(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"decision-multi-{uuid4()}@example.com",
        display_name="Decision Multi Source User",
    )

    db_session.add(user)
    await db_session.flush()

    chunks = await _create_source_chunks(
        db_session,
        user_id=user.id,
        count=2,
    )

    decision = await DecisionService().create_from_candidate(
        db_session,
        user_id=user.id,
        candidate=_candidate(
            chunks[0].id,
            chunks[1].id,
        ),
    )

    result = await db_session.scalars(
        select(DecisionSource).where(
            DecisionSource.decision_id == decision.id,
        )
    )

    sources = result.all()

    assert len(sources) == 2
    assert {source.chunk_id for source in sources} == {
        chunks[0].id,
        chunks[1].id,
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_decision_deduplicates_sources(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"decision-dedupe-{uuid4()}@example.com",
        display_name="Decision Dedupe User",
    )

    db_session.add(user)
    await db_session.flush()

    chunks = await _create_source_chunks(
        db_session,
        user_id=user.id,
    )

    decision = await DecisionService().create_from_candidate(
        db_session,
        user_id=user.id,
        candidate=_candidate(
            chunks[0].id,
            chunks[0].id,
        ),
    )

    result = await db_session.scalars(
        select(DecisionSource).where(
            DecisionSource.decision_id == decision.id,
        )
    )

    sources = result.all()

    assert len(sources) == 1
    assert sources[0].chunk_id == chunks[0].id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_decision_can_be_linked_to_project(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"decision-project-{uuid4()}@example.com",
        display_name="Decision Project User",
    )

    db_session.add(user)
    await db_session.flush()

    project = Project(
        user_id=user.id,
        name="Database Migration",
        description="Database architecture work.",
    )

    db_session.add(project)
    await db_session.flush()

    chunks = await _create_source_chunks(
        db_session,
        user_id=user.id,
    )

    decision = await DecisionService().create_from_candidate(
        db_session,
        user_id=user.id,
        candidate=_candidate(chunks[0].id),
        project_id=project.id,
    )

    assert decision.project_id == project.id

    stored_decision = await db_session.scalar(
        select(Decision).where(
            Decision.id == decision.id,
        )
    )

    assert stored_decision is not None
    assert stored_decision.project_id == project.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_decision_cannot_use_foreign_source_chunk(
    db_session: AsyncSession,
) -> None:
    owner = User(
        email=f"decision-owner-{uuid4()}@example.com",
        display_name="Decision Owner",
    )

    foreign_user = User(
        email=f"decision-foreign-{uuid4()}@example.com",
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
        await DecisionService().create_from_candidate(
            db_session,
            user_id=owner.id,
            candidate=_candidate(
                foreign_chunks[0].id,
            ),
        )

    stored_decision = await db_session.scalar(
        select(Decision).where(
            Decision.user_id == owner.id,
        )
    )

    assert stored_decision is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_decision_cannot_use_foreign_project(
    db_session: AsyncSession,
) -> None:
    owner = User(
        email=f"decision-project-owner-{uuid4()}@example.com",
        display_name="Decision Project Owner",
    )

    foreign_user = User(
        email=f"decision-project-foreign-{uuid4()}@example.com",
        display_name="Foreign Project User",
    )

    db_session.add_all([owner, foreign_user])
    await db_session.flush()

    foreign_project = Project(
        user_id=foreign_user.id,
        name="Foreign Project",
        description="Should not be accessible.",
    )

    db_session.add(foreign_project)
    await db_session.flush()

    chunks = await _create_source_chunks(
        db_session,
        user_id=owner.id,
    )

    with pytest.raises(
        ValueError,
        match="Project does not belong to the user.",
    ):
        await DecisionService().create_from_candidate(
            db_session,
            user_id=owner.id,
            candidate=_candidate(chunks[0].id),
            project_id=foreign_project.id,
        )

    stored_decision = await db_session.scalar(
        select(Decision).where(
            Decision.user_id == owner.id,
        )
    )

    assert stored_decision is None