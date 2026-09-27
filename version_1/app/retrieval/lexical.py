from __future__ import annotations

import uuid

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.retrieval.models import RetrievalResult


class LexicalRetriever:
    """Retrieve document chunks using PostgreSQL full-text search."""

    def __init__(self, language: str = "english") -> None:
        self.language = language

    async def search(
        self,
        session: AsyncSession,
        query: str,
        top_k: int = 5,
        project_id: uuid.UUID | None = None,
        document_id: uuid.UUID | None = None,
        source_type: str | None = None,
    ) -> list[RetrievalResult]:
        if not query.strip():
            raise ValueError("Query must not be empty.")

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        document_text = func.to_tsvector(
            self.language,
            DocumentChunk.content,
        )

        query_text = func.websearch_to_tsquery(
            self.language,
            " OR ".join(query.split()),
        )

        rank = func.ts_rank_cd(
            document_text,
            query_text,
        ).label("similarity")

        statement = (
            select(
                DocumentChunk,
                rank,
            )
            .join(
                Document,
                Document.id == DocumentChunk.document_id,
            )
            .where(
                document_text.op("@@")(query_text)
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
            .order_by(rank.desc())
            .limit(top_k)
        )

        result = await session.execute(statement)

        return [
            RetrievalResult(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                content=chunk.content,
                similarity=float(similarity),
                metadata=chunk.chunk_metadata,
            )
            for chunk, similarity in result
        ]