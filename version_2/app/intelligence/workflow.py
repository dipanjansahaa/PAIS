
"""Orchestrate structured extraction and persistence for one document."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.intelligence.persistence_service import (
    IntelligencePersistenceResult,
    IntelligencePersistenceService,
)
from app.intelligence.service import IntelligenceExtractionService
from app.retrieval.models import RetrievalResult


class IntelligenceWorkflowService:
    """Extract and persist intelligence from a user's document."""

    def __init__(
        self,
        *,
        extraction_service: IntelligenceExtractionService,
        persistence_service: IntelligencePersistenceService,
    ) -> None:
        self.extraction_service = extraction_service
        self.persistence_service = persistence_service

    async def extract_and_persist(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        document_id: UUID,
    ) -> IntelligencePersistenceResult:
        """Extract from owned document chunks without committing."""

        statement = (
            select(DocumentChunk)
            .join(
                Document,
                Document.id == DocumentChunk.document_id,
            )
            .where(
                DocumentChunk.document_id == document_id,
                Document.user_id == user_id,
            )
            .order_by(DocumentChunk.chunk_index)
        )

        chunks = (await session.scalars(statement)).all()

        results = [
            RetrievalResult(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                content=chunk.content,
                similarity=1.0,
                metadata=chunk.chunk_metadata,
            )
            for chunk in chunks
        ]

        if not results:
            return IntelligencePersistenceResult()

        extraction = await self.extraction_service.extract(results)

        return await self.persistence_service.persist(
            session,
            user_id=user_id,
            intelligence=extraction.intelligence,
        )
