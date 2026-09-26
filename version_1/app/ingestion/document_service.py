from __future__ import annotations

import hashlib
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.ingestion.chunker import DocumentChunker
from app.ingestion.normalizer import DocumentNormalizer
from app.ingestion.parser import get_parser
from app.ingestion.service import IngestionService


class DocumentIngestionService:
    """Orchestrates the complete document ingestion pipeline."""

    def __init__(
        self,
        ingestion_service: IngestionService,
        normalizer: DocumentNormalizer,
        chunker: DocumentChunker,
    ) -> None:
        self.ingestion_service = ingestion_service
        self.normalizer = normalizer
        self.chunker = chunker

    async def ingest(
        self,
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        title: str,
        content: bytes,
        mime_type: str,
        source_type: str,
        file_name: str | None = None,
        project_id: uuid.UUID | None = None,
    ) -> Document:
        """Parse, normalize, chunk, embed, and persist a document."""

        if not title.strip():
            raise ValueError("Document title must not be empty.")

        if not content:
            raise ValueError("Document content must not be empty.")

        parser = get_parser(mime_type)

        raw_text = parser.parse(
            content=content,
            mime_type=mime_type,
        )

        normalized_text = self.normalizer.normalize(raw_text)

        if not normalized_text:
            raise ValueError(
                "Document contains no usable text after normalization."
            )

        content_hash = hashlib.sha256(content).hexdigest()

        document = Document(
            user_id=user_id,
            project_id=project_id,
            title=title.strip(),
            source_type=source_type,
            file_name=file_name,
            mime_type=mime_type.strip().lower(),
            content_hash=content_hash,
            raw_text=normalized_text,
        )

        session.add(document)
        await session.flush()

        text_chunks = self.chunker.chunk(normalized_text)

        if not text_chunks:
            raise ValueError(
                "Document produced no chunks."
            )

        chunks = [
            DocumentChunk(
                document_id=document.id,
                chunk_index=chunk.index,
                content=chunk.content,
            )
            for chunk in text_chunks
        ]

        await self.ingestion_service.ingest_chunks(
            session=session,
            chunks=chunks,
        )

        return document