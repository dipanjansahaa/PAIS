from __future__ import annotations

import pytest

from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.user import User
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.lexical import LexicalRetriever
from app.retrieval.models import RetrievalResult
from app.retrieval.vector import VectorRetriever
from app.database.models.project import Project
from app.retrieval.fusion import RRFFusion


class FakeEmbeddingProvider:
    dimension = 384

    async def embed_query(self, text: str) -> list[float]:
        return [0.1] * self.dimension


# @pytest.fixture
# def hybrid_retriever() -> HybridRetriever:
#     return HybridRetriever(
#         vector_retriever=VectorRetriever(
#             embedding_provider=FakeEmbeddingProvider(),
#         ),
#         lexical_retriever=LexicalRetriever(),
#     )


@pytest.fixture
def hybrid_retriever():
    return HybridRetriever(
        vector_retriever=VectorRetriever(
            embedding_provider=FakeEmbeddingProvider()
        ),
        lexical_retriever=LexicalRetriever(),
        fusion=RRFFusion(k=60),
    )


async def create_document_with_chunks(
    db_session,
    *,
    title: str,
    chunks: list[dict],
) -> tuple[Document, list[DocumentChunk]]:
    user = User(
        email=None,
        display_name=f"Hybrid Test User - {title}",
    )

    db_session.add(user)
    await db_session.flush()

    document = Document(
        user_id=user.id,
        title=title,
        source_type="text",
        content_hash=f"hybrid-{title}",
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
            embedding=chunk.get("embedding"),
        )
        for index, chunk in enumerate(chunks)
    ]

    db_session.add_all(document_chunks)
    await db_session.flush()

    return document, document_chunks


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hybrid_retriever_rejects_empty_query(
    db_session,
    hybrid_retriever,
):
    with pytest.raises(
        ValueError,
        match="Query must not be empty",
    ):
        await hybrid_retriever.search(
            session=db_session,
            query="",
            top_k=5,
        )


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("top_k", [0, -1, -5])
async def test_hybrid_retriever_rejects_invalid_top_k(
    db_session,
    hybrid_retriever,
    top_k,
):
    with pytest.raises(
        ValueError,
        match="top_k must be greater than zero",
    ):
        await hybrid_retriever.search(
            session=db_session,
            query="database",
            top_k=top_k,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hybrid_retriever_combines_vector_and_lexical_results(
    db_session,
    hybrid_retriever,
):
    _, chunks = await create_document_with_chunks(
        db_session,
        title="Hybrid Combination Test",
        chunks=[
            {
                "content": "PostgreSQL is the primary database.",
                "embedding": [0.1] * 384,
                "metadata": {"source": "vector-and-lexical"},
            },
            {
                "content": "Docker is used for application deployment.",
                "embedding": [0.2] * 384,
                "metadata": {"source": "lexical"},
            },
        ],
    )

    results = await hybrid_retriever.search(
        session=db_session,
        query="PostgreSQL",
        top_k=5,
    )

    assert results

    returned_chunk_ids = {
        result.chunk_id
        for result in results
    }

    assert chunks[0].id in returned_chunk_ids


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hybrid_retriever_removes_duplicate_chunks(
    db_session,
    hybrid_retriever,
):
    _, chunks = await create_document_with_chunks(
        db_session,
        title="Hybrid Deduplication Test",
        chunks=[
            {
                "content": "PostgreSQL is used as the database.",
                "embedding": [0.1] * 384,
            },
        ],
    )

    results = await hybrid_retriever.search(
        session=db_session,
        query="PostgreSQL",
        top_k=5,
    )

    returned_chunk_ids = [
        result.chunk_id
        for result in results
    ]

    assert returned_chunk_ids.count(chunks[0].id) == 1
    assert len(results) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hybrid_retriever_respects_top_k(
    db_session,
    hybrid_retriever,
):
    await create_document_with_chunks(
        db_session,
        title="Hybrid Top K Test",
        chunks=[
            {
                "content": "PostgreSQL database information one.",
                "embedding": [0.1] * 384,
            },
            {
                "content": "PostgreSQL database information two.",
                "embedding": [0.2] * 384,
            },
            {
                "content": "PostgreSQL database information three.",
                "embedding": [0.3] * 384,
            },
        ],
    )

    results = await hybrid_retriever.search(
        session=db_session,
        query="PostgreSQL",
        top_k=2,
    )

    assert len(results) <= 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hybrid_retriever_returns_shared_retrieval_result(
    db_session,
    hybrid_retriever,
):
    document, chunks = await create_document_with_chunks(
        db_session,
        title="Hybrid Result Test",
        chunks=[
            {
                "content": "PostgreSQL is the project database.",
                "embedding": [0.1] * 384,
                "metadata": {
                    "source": "hybrid-test",
                    "type": "technology",
                },
            },
        ],
    )

    results = await hybrid_retriever.search(
        session=db_session,
        query="PostgreSQL",
        top_k=5,
    )

    assert len(results) == 1

    result = results[0]

    assert isinstance(result, RetrievalResult)
    assert result.chunk_id == chunks[0].id
    assert result.document_id == document.id
    assert result.content == chunks[0].content
    assert isinstance(result.similarity, float)
    assert result.metadata == {
        "source": "hybrid-test",
        "type": "technology",
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hybrid_retriever_filters_by_project_id(
    db_session,
    hybrid_retriever,
):
    user = User(
        email=None,
        display_name="Hybrid Project Filter User",
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
        content_hash="hybrid-project-a",
        raw_text="PostgreSQL Project A",
    )

    document_b = Document(
        user_id=user.id,
        project_id=project_b.id,
        title="Project B Document",
        source_type="text",
        content_hash="hybrid-project-b",
        raw_text="PostgreSQL Project B",
    )

    db_session.add_all([document_a, document_b])
    await db_session.flush()

    chunk_a = DocumentChunk(
        document_id=document_a.id,
        chunk_index=0,
        content="PostgreSQL is used by Project A.",
        embedding=[0.1] * 384,
    )

    chunk_b = DocumentChunk(
        document_id=document_b.id,
        chunk_index=0,
        content="PostgreSQL is used by Project B.",
        embedding=[0.1] * 384,
    )

    db_session.add_all([chunk_a, chunk_b])
    await db_session.flush()

    results = await hybrid_retriever.search(
        session=db_session,
        query="PostgreSQL",
        top_k=5,
        project_id=project_a.id,
    )

    assert len(results) == 1
    assert results[0].chunk_id == chunk_a.id
    assert results[0].document_id == document_a.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hybrid_retriever_filters_by_document_id(
    db_session,
    hybrid_retriever,
):
    user = User(
        email=None,
        display_name="Hybrid Document Filter User",
    )

    db_session.add(user)
    await db_session.flush()

    document_a = Document(
        user_id=user.id,
        title="Document A",
        source_type="text",
        content_hash="hybrid-document-a",
        raw_text="PostgreSQL Document A",
    )

    document_b = Document(
        user_id=user.id,
        title="Document B",
        source_type="text",
        content_hash="hybrid-document-b",
        raw_text="PostgreSQL Document B",
    )

    db_session.add_all([document_a, document_b])
    await db_session.flush()

    chunk_a = DocumentChunk(
        document_id=document_a.id,
        chunk_index=0,
        content="PostgreSQL is used in Document A.",
        embedding=[0.1] * 384,
    )

    chunk_b = DocumentChunk(
        document_id=document_b.id,
        chunk_index=0,
        content="PostgreSQL is used in Document B.",
        embedding=[0.1] * 384,
    )

    db_session.add_all([chunk_a, chunk_b])
    await db_session.flush()

    results = await hybrid_retriever.search(
        session=db_session,
        query="PostgreSQL",
        top_k=5,
        document_id=document_a.id,
    )

    assert len(results) == 1
    assert results[0].chunk_id == chunk_a.id
    assert results[0].document_id == document_a.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hybrid_retriever_filters_by_source_type(
    db_session,
    hybrid_retriever,
):
    user = User(
        email=None,
        display_name="Hybrid Source Type Filter User",
    )

    db_session.add(user)
    await db_session.flush()

    document_a = Document(
        user_id=user.id,
        title="Meeting Transcript",
        source_type="meeting_transcript",
        content_hash="hybrid-source-type-a",
        raw_text="PostgreSQL meeting transcript",
    )

    document_b = Document(
        user_id=user.id,
        title="Personal Note",
        source_type="note",
        content_hash="hybrid-source-type-b",
        raw_text="PostgreSQL personal note",
    )

    db_session.add_all([document_a, document_b])
    await db_session.flush()

    chunk_a = DocumentChunk(
        document_id=document_a.id,
        chunk_index=0,
        content="PostgreSQL was discussed in the meeting.",
        embedding=[0.1] * 384,
    )

    chunk_b = DocumentChunk(
        document_id=document_b.id,
        chunk_index=0,
        content="PostgreSQL was mentioned in my note.",
        embedding=[0.1] * 384,
    )

    db_session.add_all([chunk_a, chunk_b])
    await db_session.flush()

    results = await hybrid_retriever.search(
        session=db_session,
        query="PostgreSQL",
        top_k=5,
        source_type="meeting_transcript",
    )

    assert len(results) == 1
    assert results[0].chunk_id == chunk_a.id
    assert results[0].document_id == document_a.id