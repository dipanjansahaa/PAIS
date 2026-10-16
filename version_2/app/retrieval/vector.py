from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.retrieval.models import RetrievalResult


class VectorRetriever:
    """Retrieve document chunks using vector similarity search."""

    def __init__(self, embedding_provider) -> None:
        self.embedding_provider = embedding_provider

    async def search(
        self,
        session: AsyncSession,
        query: str,
        top_k: int = 5,
        user_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
        document_id: uuid.UUID | None = None,
        source_type: str | None = None,
    ) -> list[RetrievalResult]:
        if not query.strip():
            raise ValueError("Query must not be empty.")

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        if user_id is None:
            raise ValueError("user_id is required.")

        query_embedding = await self.embedding_provider.embed_query(query)

        distance = DocumentChunk.embedding.cosine_distance(
            query_embedding
        )

        statement = (
            select(
                DocumentChunk,
                distance.label("distance"),
            )
            .join(
                Document,
                Document.id == DocumentChunk.document_id,
            )
            .where(
                Document.user_id == user_id,
                DocumentChunk.embedding.is_not(None),
            )
        )

        if project_id is not None:
            statement = statement.where(
                Document.project_id == project_id
            )

        if document_id is not None:
            statement = statement.where(
                DocumentChunk.document_id == document_id
            )

        if source_type is not None:
            statement = statement.where(
                Document.source_type == source_type
            )

        statement = (
            statement
            .order_by(distance)
            .limit(top_k)
        )

        result = await session.execute(statement)

        return [
            RetrievalResult(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                content=chunk.content,
                similarity=1.0 - float(distance_value),
                metadata=chunk.chunk_metadata,
            )
            for chunk, distance_value in result
        ]