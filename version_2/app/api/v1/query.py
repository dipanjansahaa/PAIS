"""Grounded query API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.api.v1.schemas.query import (
    QueryChunkResponse,
    QueryMemoryResponse,
    QueryMemorySourceResponse,
    QueryRelationshipResponse,
    QueryRelationshipSourceResponse,
    QueryRequest,
    QueryResponse,
    QuerySourceResponse,
)
from app.api.v1.search import get_search_service
from app.core.config import settings
from app.database.models.user import User
from app.database.session import get_db
from app.llm.factory import get_llm_provider
from app.llm.tracked import TrackedLLMProvider
from app.memory.service import MemoryService
from app.observability.models import ModelRunOperation
from app.query.context import ContextBuilder
from app.query.service import QueryEntityNotFoundError, QueryService

router = APIRouter(
    prefix="/query",
    tags=["query"],
)


def get_query_service(
    db_session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QueryService:
    """Return the production query service."""

    search_service = get_search_service()
    context_builder = ContextBuilder()

    llm_provider = TrackedLLMProvider(
        provider=get_llm_provider(),
        user_id=current_user.id,
        operation=ModelRunOperation.QUERY,
        provider_name=settings.llm_provider,
        session=db_session,
    )

    return QueryService(
        search_service=search_service,
        context_builder=context_builder,
        llm_provider=llm_provider,
        memory_service=MemoryService(),
    )


@router.post(
    "",
    response_model=QueryResponse,
)
async def query(
    request: QueryRequest,
    db_session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    query_service: QueryService = Depends(get_query_service),
) -> QueryResponse:
    """Answer a user query using document and memory evidence."""

    try:
        result = await query_service.query(
            db_session,
            user_id=current_user.id,
            query=request.query,
            top_k=request.top_k,
            project_id=request.project_id,
            document_id=request.document_id,
            source_type=request.source_type,
            temperature=request.temperature,
            as_of=request.as_of,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
        )
    except QueryEntityNotFoundError as exc:
        # Do not reveal whether a seed entity exists for another user.
        raise HTTPException(
            status_code=404,
            detail=("Entity does not exist or does not belong to the authenticated user."),
        ) from exc

    return QueryResponse(
        query=result.query,
        answer=result.answer,
        sources=[
            QuerySourceResponse(
                citation_id=source.citation_id,
                document_id=source.document_id,
                chunks=[
                    QueryChunkResponse(
                        citation_id=chunk.citation_id,
                        chunk_id=chunk.chunk_id,
                        document_id=chunk.document_id,
                        content=chunk.content,
                        score=chunk.similarity,
                        metadata=chunk.metadata,
                    )
                    for chunk in source.chunks
                ],
            )
            for source in result.sources
        ],
        memories=[
            QueryMemoryResponse(
                citation_id=memory.citation_id,
                memory_id=memory.memory_id,
                memory_type=memory.memory_type,
                content=memory.content,
                status=memory.status,
                valid_from=memory.valid_from,
                valid_until=memory.valid_until,
                confidence=memory.confidence,
                sources=[
                    QueryMemorySourceResponse(
                        source_kind=source.source_kind,
                        document_id=source.document_id,
                        chunk_id=source.chunk_id,
                        source_reference=source.source_reference,
                        evidence_text=source.evidence_text,
                    )
                    for source in memory.sources
                ],
            )
            for memory in result.memories
        ],
        relationships=[
            QueryRelationshipResponse(
                citation_id=relationship.citation_id,
                relationship_id=relationship.relationship_id,
                source_type=relationship.source_type,
                source_id=relationship.source_id,
                source_label=relationship.source_label,
                relationship_type=relationship.relationship_type,
                target_type=relationship.target_type,
                target_id=relationship.target_id,
                target_label=relationship.target_label,
                valid_from=relationship.valid_from,
                valid_until=relationship.valid_until,
                sources=[
                    QueryRelationshipSourceResponse(
                        citation_id=source.citation_id,
                        chunk_id=source.chunk_id,
                        document_id=source.document_id,
                        document_title=source.document_title,
                        content=source.content,
                    )
                    for source in relationship.sources
                ],
            )
            for relationship in result.relationships
        ],
        model=result.model,
        latency_ms=result.latency_ms,
        truncated=result.truncated,
    )
