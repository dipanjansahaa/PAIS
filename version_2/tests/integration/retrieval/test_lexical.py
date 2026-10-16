from __future__ import annotations

import pytest

from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.user import User
from app.retrieval.lexical import LexicalRetriever
from app.retrieval.models import RetrievalResult
from app.database.models.project import Project


@pytest.fixture
def retriever() -> LexicalRetriever:
    return LexicalRetriever()


async def create_document_with_chunks(
    db_session,
    *,
    title: str,
    chunks: list[dict],
) -> tuple[Document, list[DocumentChunk]]:
    user = User(
        email=None,
        display_name=f"Lexical Test User - {title}",
    )

    db_session.add(user)
    await db_session.flush()

    document = Document(
        user_id=user.id,
        title=title,
        source_type="text",
        content_hash=f"lexical-{title}",
        raw_text="\n\n".join(
            chunk["content"] for chunk in chunks
        ),
    )

    db_session.add(document)
    await db_session.flush()

    document_chunks = [
        DocumentChunk(
            document_id=document.id,
            chunk_index=index,
            content=chunk["content"],
            token_count=chunk.get("token_count"),
            chunk_metadata=chunk.get("metadata"),
        )
        for index, chunk in enumerate(chunks)
    ]

    db_session.add_all(document_chunks)
    await db_session.flush()

    return document, document_chunks


@pytest.mark.integration
@pytest.mark.asyncio
async def test_lexical_retriever_rejects_empty_query(
    db_session,
    retriever,
):
    with pytest.raises(
        ValueError,
        match="Query must not be empty",
    ):
        await retriever.search(
            session=db_session,
            query="",
            top_k=5,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_lexical_retriever_rejects_whitespace_query(
    db_session,
    retriever,
):
    with pytest.raises(
        ValueError,
        match="Query must not be empty",
    ):
        await retriever.search(
            session=db_session,
            query="   ",
            top_k=5,
        )


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("top_k", [0, -1, -5])
async def test_lexical_retriever_rejects_invalid_top_k(
    db_session,
    retriever,
    top_k,
):
    with pytest.raises(
        ValueError,
        match="top_k must be greater than zero",
    ):
        await retriever.search(
            session=db_session,
            query="lexical",
            top_k=top_k,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_lexical_retriever_returns_empty_list_when_no_match_exists(
    db_session,
    retriever,
):
    user = User(
        email=None,
        display_name="Lexical Empty Result User",
    )

    db_session.add(user)
    await db_session.flush()

    results = await retriever.search(
        session=db_session,
        query="nonexistentlexicalkeyword",
        top_k=5,
        user_id=user.id,
    )

    assert results == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_lexical_retriever_returns_exact_keyword_match(
    db_session,
    retriever,
):
    document, chunks = await create_document_with_chunks(
        db_session,
        title="Exact Keyword Test",
        chunks=[
            {
                "content": (
                    "The project uses PostgreSQL as its primary "
                    "database."
                ),
                "metadata": {"type": "technology"},
            },
            {
                "content": (
                    "The application is deployed using Docker."
                ),
                "metadata": {"type": "deployment"},
            },
        ],
    )

    results = await retriever.search(
        session=db_session,
        query="PostgreSQL",
        top_k=5,
        user_id=document.user_id,
    )

    assert len(results) == 1
    assert results[0].chunk_id == chunks[0].id
    assert "PostgreSQL" in results[0].content


@pytest.mark.integration
@pytest.mark.asyncio
async def test_lexical_retriever_ranks_more_relevant_match_first(
    db_session,
    retriever,
):
    document, chunks = await create_document_with_chunks(
        db_session,
        title="Ranking Test",
        chunks=[
            {
                "content": (
                    "PostgreSQL is the PostgreSQL database selected "
                    "for the project."
                ),
                "metadata": {"rank": "high"},
            },
            {
                "content": (
                    "The project documentation mentions PostgreSQL."
                ),
                "metadata": {"rank": "low"},
            },
        ],
    )

    results = await retriever.search(
        session=db_session,
        query="PostgreSQL",
        top_k=5,
        user_id=document.user_id,
    )

    assert len(results) == 2

    assert results[0].chunk_id == chunks[0].id
    assert results[1].chunk_id == chunks[1].id

    assert results[0].similarity > results[1].similarity


@pytest.mark.integration
@pytest.mark.asyncio
async def test_lexical_retriever_respects_top_k(
    db_session,
    retriever,
):
    document, chunks = await create_document_with_chunks(
        db_session,
        title="Top K Test",
        chunks=[
            {
                "content": (
                    "toplimit PostgreSQL database information one."
                ),
            },
            {
                "content": (
                    "toplimit PostgreSQL database information two."
                ),
            },
            {
                "content": (
                    "toplimit PostgreSQL database information three."
                ),
            },
        ],
    )

    results = await retriever.search(
        session=db_session,
        query="toplimit",
        top_k=2,
        user_id=document.user_id,
    )

    assert len(results) == 2

    returned_chunk_ids = {
        result.chunk_id
        for result in results
    }

    expected_chunk_ids = {
        chunks[0].id,
        chunks[1].id,
        chunks[2].id,
    }

    assert returned_chunk_ids.issubset(expected_chunk_ids)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_lexical_retriever_returns_retrieval_result_fields(
    db_session,
    retriever,
):
    document, chunks = await create_document_with_chunks(
        db_session,
        title="Retrieval Result Test",
        chunks=[
            {
                "content": (
                    "lexicalresult PostgreSQL database information."
                ),
                "token_count": 5,
                "metadata": {
                    "source": "test",
                    "type": "decision",
                },
            },
        ],
    )

    results = await retriever.search(
        session=db_session,
        query="lexicalresult",
        top_k=5,
        user_id=document.user_id,
    )

    assert len(results) == 1

    result = results[0]

    assert isinstance(result, RetrievalResult)

    assert result.chunk_id == chunks[0].id
    assert result.document_id == document.id
    assert result.content == chunks[0].content
    assert isinstance(result.similarity, float)
    assert result.similarity > 0
    assert result.metadata == {
        "source": "test",
        "type": "decision",
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_lexical_retriever_filters_by_project_id(
    db_session,
    retriever,
):
    user = User(
        email=None,
        display_name="Lexical Project Filter User",
    )

    db_session.add(user)
    await db_session.flush()

    project_a = Project(
        user_id=user.id,
        name="Project A",
    )

    project_b = Project(
        user_id=user.id,
        name="Project B",
    )

    db_session.add_all([project_a, project_b])
    await db_session.flush()

    document_a = Document(
        user_id=user.id,
        project_id=project_a.id,
        title="Project A Document",
        source_type="text",
        content_hash="lexical-project-a",
        raw_text="PostgreSQL Project A",
    )

    document_b = Document(
        user_id=user.id,
        project_id=project_b.id,
        title="Project B Document",
        source_type="text",
        content_hash="lexical-project-b",
        raw_text="PostgreSQL Project B",
    )

    db_session.add_all([document_a, document_b])
    await db_session.flush()

    chunk_a = DocumentChunk(
        document_id=document_a.id,
        chunk_index=0,
        content="PostgreSQL is used by Project A.",
    )

    chunk_b = DocumentChunk(
        document_id=document_b.id,
        chunk_index=0,
        content="PostgreSQL is used by Project B.",
    )

    db_session.add_all([chunk_a, chunk_b])
    await db_session.flush()

    results = await retriever.search(
        session=db_session,
        query="PostgreSQL",
        top_k=5,
        user_id=user.id,
        project_id=project_a.id,
    )

    assert len(results) == 1
    assert results[0].chunk_id == chunk_a.id
    assert results[0].document_id == document_a.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_lexical_retriever_filters_by_document_id(
    db_session,
    retriever,
):
    user = User(
        email=None,
        display_name="Lexical Document Filter User",
    )

    db_session.add(user)
    await db_session.flush()

    document_a = Document(
        user_id=user.id,
        title="Document A",
        source_type="text",
        content_hash="lexical-document-a",
        raw_text="PostgreSQL Document A",
    )

    document_b = Document(
        user_id=user.id,
        title="Document B",
        source_type="text",
        content_hash="lexical-document-b",
        raw_text="PostgreSQL Document B",
    )

    db_session.add_all([document_a, document_b])
    await db_session.flush()

    chunk_a = DocumentChunk(
        document_id=document_a.id,
        chunk_index=0,
        content="PostgreSQL is used in Document A.",
    )

    chunk_b = DocumentChunk(
        document_id=document_b.id,
        chunk_index=0,
        content="PostgreSQL is used in Document B.",
    )

    db_session.add_all([chunk_a, chunk_b])
    await db_session.flush()

    results = await retriever.search(
        session=db_session,
        query="PostgreSQL",
        top_k=5,
        user_id=user.id,
        document_id=document_a.id,
    )

    assert len(results) == 1
    assert results[0].chunk_id == chunk_a.id
    assert results[0].document_id == document_a.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_lexical_retriever_filters_by_source_type(
    db_session,
    retriever,
):
    user = User(
        email=None,
        display_name="Lexical Source Type Filter User",
    )

    db_session.add(user)
    await db_session.flush()

    document_a = Document(
        user_id=user.id,
        title="Meeting Transcript",
        source_type="meeting_transcript",
        content_hash="lexical-source-type-a",
        raw_text="PostgreSQL meeting transcript",
    )

    document_b = Document(
        user_id=user.id,
        title="Personal Note",
        source_type="note",
        content_hash="lexical-source-type-b",
        raw_text="PostgreSQL personal note",
    )

    db_session.add_all([document_a, document_b])
    await db_session.flush()

    chunk_a = DocumentChunk(
        document_id=document_a.id,
        chunk_index=0,
        content="PostgreSQL was discussed in the meeting.",
    )

    chunk_b = DocumentChunk(
        document_id=document_b.id,
        chunk_index=0,
        content="PostgreSQL was mentioned in my note.",
    )

    db_session.add_all([chunk_a, chunk_b])
    await db_session.flush()

    results = await retriever.search(
        session=db_session,
        query="PostgreSQL",
        top_k=5,
        user_id=user.id,
        source_type="meeting_transcript",
    )

    assert len(results) == 1
    assert results[0].chunk_id == chunk_a.id
    assert results[0].document_id == document_a.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_lexical_retriever_isolates_users(
    db_session,
    retriever,
):
    user_a = User(
        email=None,
        display_name="Lexical User A",
    )

    user_b = User(
        email=None,
        display_name="Lexical User B",
    )

    db_session.add_all([user_a, user_b])
    await db_session.flush()

    document_a = Document(
        user_id=user_a.id,
        title="User A Document",
        source_type="text",
        content_hash="lexical-user-a",
        raw_text="PostgreSQL User A",
    )

    document_b = Document(
        user_id=user_b.id,
        title="User B Document",
        source_type="text",
        content_hash="lexical-user-b",
        raw_text="PostgreSQL User B",
    )

    db_session.add_all([document_a, document_b])
    await db_session.flush()

    chunk_a = DocumentChunk(
        document_id=document_a.id,
        chunk_index=0,
        content="PostgreSQL information belonging to User A.",
    )

    chunk_b = DocumentChunk(
        document_id=document_b.id,
        chunk_index=0,
        content="PostgreSQL information belonging to User B.",
    )

    db_session.add_all([chunk_a, chunk_b])
    await db_session.flush()

    results = await retriever.search(
        session=db_session,
        query="PostgreSQL",
        top_k=5,
        user_id=user_a.id,
    )

    returned_ids = {
        result.chunk_id
        for result in results
    }

    assert chunk_a.id in returned_ids
    assert chunk_b.id not in returned_ids