"""Grounded query API."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.api.v1.schemas.query import (
    QueryChunkResponse,
    QueryMemoryResponse,
    QueryMemorySourceResponse,
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
from app.query.service import QueryService

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

    result = await query_service.query(
        db_session,
        user_id=current_user.id,
        query=request.query,
        top_k=request.top_k,
        project_id=request.project_id,
        document_id=request.document_id,
        source_type=request.source_type,
        temperature=request.temperature,
    )

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
        model=result.model,
        latency_ms=result.latency_ms,
        truncated=result.truncated,
    )
