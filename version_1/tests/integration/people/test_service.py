from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.person import Person, PersonSource
from app.database.models.user import User
from app.intelligence.models import IntelligenceSource, PersonCandidate
from app.people.service import PersonService


async def _create_source_chunks(
    db_session: AsyncSession,
    *,
    user_id,
    count: int = 1,
) -> list[DocumentChunk]:
    document = Document(
        user_id=user_id,
        title="Person Source Document",
        source_type="test",
        file_name="people.txt",
        mime_type="text/plain",
        content_hash=uuid4().hex,
        raw_text="Person source material.",
    )

    db_session.add(document)
    await db_session.flush()

    chunks = [
        DocumentChunk(
            document_id=document.id,
            chunk_index=index,
            content=f"Person source {index}.",
            embedding=[1.0] + [0.0] * 383,
        )
        for index in range(count)
    ]

    db_session.add_all(chunks)
    await db_session.flush()

    return chunks


def _candidate(*chunk_ids) -> PersonCandidate:
    return PersonCandidate(
        name="Alice Smith",
        email="alice@example.com",
        sources=[
            IntelligenceSource(chunk_id=chunk_id)
            for chunk_id in chunk_ids
        ],
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_person_from_candidate_persists_person_and_provenance(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"person-{uuid4()}@example.com",
        display_name="Person Integration User",
    )

    db_session.add(user)
    await db_session.flush()

    chunks = await _create_source_chunks(
        db_session,
        user_id=user.id,
    )

    person = await PersonService().create_from_candidate(
        db_session,
        user_id=user.id,
        candidate=_candidate(chunks[0].id),
    )

    assert person.id is not None
    assert person.user_id == user.id
    assert person.name == "Alice Smith"
    assert person.email == "alice@example.com"

    stored_person = await db_session.scalar(
        select(Person).where(
            Person.id == person.id,
        )
    )

    assert stored_person is not None
    assert stored_person.user_id == user.id

    stored_source = await db_session.scalar(
        select(PersonSource).where(
            PersonSource.person_id == person.id,
            PersonSource.chunk_id == chunks[0].id,
        )
    )

    assert stored_source is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_person_with_multiple_sources(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"person-multi-{uuid4()}@example.com",
        display_name="Person Multi Source User",
    )

    db_session.add(user)
    await db_session.flush()

    chunks = await _create_source_chunks(
        db_session,
        user_id=user.id,
        count=2,
    )

    person = await PersonService().create_from_candidate(
        db_session,
        user_id=user.id,
        candidate=_candidate(
            chunks[0].id,
            chunks[1].id,
        ),
    )

    result = await db_session.scalars(
        select(PersonSource).where(
            PersonSource.person_id == person.id,
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
async def test_create_person_deduplicates_sources(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"person-dedupe-{uuid4()}@example.com",
        display_name="Person Dedupe User",
    )

    db_session.add(user)
    await db_session.flush()

    chunks = await _create_source_chunks(
        db_session,
        user_id=user.id,
    )

    person = await PersonService().create_from_candidate(
        db_session,
        user_id=user.id,
        candidate=_candidate(
            chunks[0].id,
            chunks[0].id,
        ),
    )

    result = await db_session.scalars(
        select(PersonSource).where(
            PersonSource.person_id == person.id,
        )
    )

    sources = result.all()

    assert len(sources) == 1
    assert sources[0].chunk_id == chunks[0].id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_person_cannot_use_foreign_source_chunk(
    db_session: AsyncSession,
) -> None:
    owner = User(
        email=f"person-owner-{uuid4()}@example.com",
        display_name="Person Owner",
    )

    foreign_user = User(
        email=f"person-foreign-{uuid4()}@example.com",
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
        await PersonService().create_from_candidate(
            db_session,
            user_id=owner.id,
            candidate=_candidate(
                foreign_chunks[0].id,
            ),
        )

    stored_person = await db_session.scalar(
        select(Person).where(
            Person.user_id == owner.id,
        )
    )

    assert stored_person is None