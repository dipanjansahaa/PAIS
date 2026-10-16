from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.project import Project, ProjectSource
from app.database.models.user import User
from app.intelligence.models import IntelligenceSource, ProjectCandidate
from app.projects.service import ProjectService


async def _create_source_chunks(
    db_session: AsyncSession,
    *,
    user_id,
    count: int = 1,
) -> list[DocumentChunk]:
    document = Document(
        user_id=user_id,
        title="Project Source Document",
        source_type="test",
        file_name="projects.txt",
        mime_type="text/plain",
        content_hash=uuid4().hex,
        raw_text="Project source material.",
    )

    db_session.add(document)
    await db_session.flush()

    chunks = [
        DocumentChunk(
            document_id=document.id,
            chunk_index=index,
            content=f"Project source {index}.",
            embedding=[1.0] + [0.0] * 383,
        )
        for index in range(count)
    ]

    db_session.add_all(chunks)
    await db_session.flush()

    return chunks


def _candidate(*chunk_ids) -> ProjectCandidate:
    return ProjectCandidate(
        name="PAIS Development",
        description="Build the PAIS system.",
        sources=[
            IntelligenceSource(chunk_id=chunk_id)
            for chunk_id in chunk_ids
        ],
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_project_from_candidate_persists_project_and_provenance(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"project-{uuid4()}@example.com",
        display_name="Project Integration User",
    )

    db_session.add(user)
    await db_session.flush()

    chunks = await _create_source_chunks(
        db_session,
        user_id=user.id,
    )

    project = await ProjectService().create_from_candidate(
        db_session,
        user_id=user.id,
        candidate=_candidate(chunks[0].id),
    )

    assert project.id is not None
    assert project.user_id == user.id
    assert project.name == "PAIS Development"
    assert project.description == "Build the PAIS system."
    assert project.status == "active"

    stored_project = await db_session.scalar(
        select(Project).where(
            Project.id == project.id,
        )
    )

    assert stored_project is not None
    assert stored_project.user_id == user.id

    stored_source = await db_session.scalar(
        select(ProjectSource).where(
            ProjectSource.project_id == project.id,
            ProjectSource.chunk_id == chunks[0].id,
        )
    )

    assert stored_source is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_project_with_multiple_sources(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"project-multi-{uuid4()}@example.com",
        display_name="Project Multi Source User",
    )

    db_session.add(user)
    await db_session.flush()

    chunks = await _create_source_chunks(
        db_session,
        user_id=user.id,
        count=2,
    )

    project = await ProjectService().create_from_candidate(
        db_session,
        user_id=user.id,
        candidate=_candidate(
            chunks[0].id,
            chunks[1].id,
        ),
    )

    result = await db_session.scalars(
        select(ProjectSource).where(
            ProjectSource.project_id == project.id,
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
async def test_create_project_deduplicates_sources(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"project-dedupe-{uuid4()}@example.com",
        display_name="Project Dedupe User",
    )

    db_session.add(user)
    await db_session.flush()

    chunks = await _create_source_chunks(
        db_session,
        user_id=user.id,
    )

    project = await ProjectService().create_from_candidate(
        db_session,
        user_id=user.id,
        candidate=_candidate(
            chunks[0].id,
            chunks[0].id,
        ),
    )

    result = await db_session.scalars(
        select(ProjectSource).where(
            ProjectSource.project_id == project.id,
        )
    )

    sources = result.all()

    assert len(sources) == 1
    assert sources[0].chunk_id == chunks[0].id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_project_cannot_use_foreign_source_chunk(
    db_session: AsyncSession,
) -> None:
    owner = User(
        email=f"project-owner-{uuid4()}@example.com",
        display_name="Project Owner",
    )

    foreign_user = User(
        email=f"project-foreign-{uuid4()}@example.com",
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
        await ProjectService().create_from_candidate(
            db_session,
            user_id=owner.id,
            candidate=_candidate(
                foreign_chunks[0].id,
            ),
        )

    stored_project = await db_session.scalar(
        select(Project).where(
            Project.user_id == owner.id,
        )
    )

    assert stored_project is None