from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.api.v1.schemas.documents import DocumentResponse
from app.database.models.user import User
from app.database.session import get_db
from app.embeddings.factory import get_embedding_provider
from app.ingestion.chunker import DocumentChunker
from app.ingestion.document_service import DocumentIngestionService
from app.ingestion.exceptions import DuplicateDocumentError
from app.ingestion.normalizer import DocumentNormalizer
from app.ingestion.service import IngestionService


router = APIRouter(
    prefix="/documents",
    tags=["documents"],
)


def get_document_ingestion_service() -> DocumentIngestionService:
    """Build the document ingestion service and its dependencies."""

    embedding_provider = get_embedding_provider()

    ingestion_service = IngestionService(
        embedding_provider=embedding_provider,
    )

    return DocumentIngestionService(
        ingestion_service=ingestion_service,
        normalizer=DocumentNormalizer(),
        chunker=DocumentChunker(),
    )


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    source_type: str = Form(...),
    project_id: uuid.UUID | None = Form(default=None),
    db_session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    document_service: DocumentIngestionService = Depends(
        get_document_ingestion_service,
    ),
) -> DocumentResponse:
    """Upload and ingest a document."""

    content = await file.read()

    try:
        document = await document_service.ingest(
            db_session,
            user_id=current_user.id,
            title=title,
            content=content,
            mime_type=file.content_type or "application/octet-stream",
            source_type=source_type,
            file_name=file.filename,
            project_id=project_id,
        )

        await db_session.commit()

    except DuplicateDocumentError as exc:
        await db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        await db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return DocumentResponse.model_validate(document)