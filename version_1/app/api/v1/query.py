"""Grounded query API."""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.api.v1.schemas.query import (
    QueryChunkResponse,
    QueryRequest,
    QueryResponse,
    QuerySourceResponse,
)
from app.database.models.user import User
from app.database.session import get_db
from app.llm.factory import get_llm_provider
from app.query.context import ContextBuilder
from app.query.service import QueryService
from app.retrieval.service import SearchService
from app.api.v1.search import get_search_service


router = APIRouter(
    prefix="/query",
    tags=["query"],
)


@lru_cache(maxsize=1)
def get_query_service() -> QueryService:
    """Return the production query service."""

    search_service = get_search_service()
    context_builder = ContextBuilder()
    llm_provider = get_llm_provider()

    return QueryService(
        search_service=search_service,
        context_builder=context_builder,
        llm_provider=llm_provider,
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
    """Answer a user query using grounded retrieved context."""

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
        model=result.model,
        latency_ms=result.latency_ms,
        truncated=result.truncated,
    )