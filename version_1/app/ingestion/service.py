from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.document_chunk import DocumentChunk
# from app.embeddings.factory import get_embedding_provider
from app.embeddings.base import EmbeddingProvider


# class IngestionService:
#     def __init__(self) -> None:
#         self.embedding_provider = get_embedding_provider()

class IngestionService:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self.embedding_provider = embedding_provider

    async def embed_chunks(
        self,
        chunks: list[DocumentChunk],
    ) -> None:
        if not chunks:
            return

        texts = [chunk.content for chunk in chunks]

        embeddings = await self.embedding_provider.embed_documents(
            texts
        )

        if len(embeddings) != len(chunks):
            raise RuntimeError(
                "Embedding count does not match chunk count."
            )

        expected_dimension = self.embedding_provider.dimension

        for chunk, embedding in zip(chunks, embeddings):
            actual_dimension = len(embedding)

            if actual_dimension != expected_dimension:
                raise RuntimeError(
                    f"Invalid embedding dimension for chunk "
                    f"{chunk.id}: expected {expected_dimension}, "
                    f"got {actual_dimension}."
                )

            chunk.embedding = embedding

    async def ingest_chunks(
        self,
        session: AsyncSession,
        chunks: list[DocumentChunk],
    ) -> list[DocumentChunk]:
        if not chunks:
            return []

        session.add_all(chunks)

        await session.flush()

        await self.embed_chunks(chunks)

        await session.flush()

        return chunks