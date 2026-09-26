import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.user import User
from app.embeddings.factory import get_embedding_provider
from app.ingestion.service import IngestionService
from app.retrieval.vector import VectorRetriever


@pytest.mark.asyncio
async def test_vector_retriever_with_real_embeddings(
    db_session: AsyncSession,
) -> None:
    # Arrange
    user = User(
        email=f"real-retrieval-{uuid.uuid4()}@example.com",
        display_name="Real Retrieval Test User",
    )
    db_session.add(user)
    await db_session.flush()

    document = Document(
        user_id=user.id,
        title="PAIS Architecture Notes",
        source_type="test",
        file_name="architecture.md",
        mime_type="text/markdown",
        content_hash=uuid.uuid4().hex,
        raw_text=(
            "The project uses PostgreSQL as its primary relational database.\n"
            "The backend API is implemented using FastAPI and Python.\n"
            "The application is deployed using Docker containers."
        ),
    )
    db_session.add(document)
    await db_session.flush()

    chunks = [
        DocumentChunk(
            document_id=document.id,
            chunk_index=0,
            content="The project uses PostgreSQL as its primary relational database.",
            token_count=10,
            chunk_metadata={"source": "test"},
        ),
        DocumentChunk(
            document_id=document.id,
            chunk_index=1,
            content="The backend API is implemented using FastAPI and Python.",
            token_count=9,
            chunk_metadata={"source": "test"},
        ),
        DocumentChunk(
            document_id=document.id,
            chunk_index=2,
            content="The application is deployed using Docker containers.",
            token_count=8,
            chunk_metadata={"source": "test"},
        ),
    ]

    embedding_provider = get_embedding_provider()
    ingestion_service = IngestionService(embedding_provider)

    # Generate and persist real BGE embeddings.
    await ingestion_service.ingest_chunks(
        session=db_session,
        chunks=chunks,
    )

    # Make sure embeddings were actually generated.
    assert all(chunk.embedding is not None for chunk in chunks)
    assert all(
        len(chunk.embedding) == embedding_provider.dimension
        for chunk in chunks
        if chunk.embedding is not None
    )

    # Act
    retriever = VectorRetriever(embedding_provider)

    results = await retriever.search(
        session=db_session,
        query="What database does the project use?",
        top_k=3,
    )

    # Assert
    assert len(results) == 3

    # The semantically relevant PostgreSQL chunk should rank first.
    assert "PostgreSQL" in results[0].content

    # The first result should be more similar than the remaining results.
    assert results[0].similarity > results[1].similarity
    assert results[0].similarity > results[2].similarity