from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.document_chunk import DocumentChunk
from app.database.models.user import User
from app.embeddings.base import EmbeddingProvider
from app.ingestion.chunker import DocumentChunker
from app.ingestion.document_service import DocumentIngestionService
from app.ingestion.normalizer import DocumentNormalizer
from app.ingestion.service import IngestionService


class FakeEmbeddingProvider(EmbeddingProvider):
    @property
    def model_name(self) -> str:
        return "fake-test-model"

    @property
    def dimension(self) -> int:
        return 384

    async def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        return [
            [1.0] + [0.0] * 383
            for _ in texts
        ]

    async def embed_query(
        self,
        text: str,
    ) -> list[float]:
        return [1.0] + [0.0] * 383


@pytest.mark.asyncio
async def test_document_ingestion_pipeline(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"document-ingestion-{uuid.uuid4()}@example.com",
        display_name="Document Ingestion Test User",
    )

    db_session.add(user)
    await db_session.flush()

    embedding_provider = FakeEmbeddingProvider()

    ingestion_service = IngestionService(
        embedding_provider=embedding_provider,
    )

    document_service = DocumentIngestionService(
        ingestion_service=ingestion_service,
        normalizer=DocumentNormalizer(),
        chunker=DocumentChunker(
            chunk_size=100,
            chunk_overlap=20,
        ),
    )

    content = (
        b"# Database Decision\n\n"
        b"We decided to use PostgreSQL for the project.\n\n"
        b"The backend uses FastAPI and Python."
    )

    document = await document_service.ingest(
        session=db_session,
        user_id=user.id,
        title="Architecture Decision",
        content=content,
        mime_type="text/markdown",
        source_type="test",
        file_name="architecture.md",
    )

    assert document.id is not None
    assert document.user_id == user.id
    assert document.title == "Architecture Decision"
    assert document.mime_type == "text/markdown"
    assert document.raw_text == (
        "# Database Decision\n\n"
        "We decided to use PostgreSQL for the project.\n\n"
        "The backend uses FastAPI and Python."
    )
    assert len(document.content_hash) == 64

    result = await db_session.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document.id)
        .order_by(DocumentChunk.chunk_index)
    )

    chunks = list(result.scalars())

    assert chunks

    assert [chunk.chunk_index for chunk in chunks] == list(
        range(len(chunks))
    )

    assert all(chunk.embedding is not None for chunk in chunks)

    assert all(
        len(chunk.embedding) == embedding_provider.dimension
        for chunk in chunks
        if chunk.embedding is not None
    )