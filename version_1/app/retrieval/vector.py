from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.document_chunk import DocumentChunk
from app.embeddings.base import EmbeddingProvider
from app.retrieval.models import RetrievalResult


class VectorRetriever:
    """Retrieve document chunks using vector similarity."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self.embedding_provider = embedding_provider

    async def search(
        self,
        session: AsyncSession,
        query: str,
        top_k: int = 5,
    ) -> list[RetrievalResult]:
        if not query.strip():
            raise ValueError("Query must not be empty.")

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        query_embedding = await self.embedding_provider.embed_query(
            query
        )

        distance = DocumentChunk.embedding.cosine_distance(
            query_embedding
        )

        similarity = (1 - distance).label("similarity")

        statement = (
            select(
                DocumentChunk.id,
                DocumentChunk.document_id,
                DocumentChunk.content,
                DocumentChunk.chunk_metadata,
                similarity,
            )
            .where(DocumentChunk.embedding.is_not(None))
            .order_by(distance)
            .limit(top_k)
        )

        result = await session.execute(statement)

        return [
            RetrievalResult(
                chunk_id=row.id,
                document_id=row.document_id,
                content=row.content,
                similarity=float(row.similarity),
                metadata=row.chunk_metadata,
            )
            for row in result
        ]