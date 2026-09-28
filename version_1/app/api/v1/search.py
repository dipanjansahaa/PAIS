"""Search API endpoints."""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.api.v1.schemas.search import (
    SearchRequest,
    SearchResponse,
    SearchResultResponse,
)
from app.database.models.user import User
from app.database.session import get_db
from app.embeddings.factory import get_embedding_provider
from app.retrieval.fusion import RRFFusion
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.lexical import LexicalRetriever
from app.retrieval.service import SearchService
from app.retrieval.vector import VectorRetriever


router = APIRouter(
    prefix="/search",
    tags=["search"],
)


@lru_cache(maxsize=1)
def get_search_service() -> SearchService:
    """Return the production search service."""

    embedding_provider = get_embedding_provider()

    vector_retriever = VectorRetriever(
        embedding_provider=embedding_provider,
    )

    lexical_retriever = LexicalRetriever()

    hybrid_retriever = HybridRetriever(
        vector_retriever=vector_retriever,
        lexical_retriever=lexical_retriever,
        fusion=RRFFusion(k=60),
    )

    return SearchService(
        retriever=hybrid_retriever,
    )


@router.post(
    "",
    response_model=SearchResponse,
)
async def search(
    request: SearchRequest,
    db_session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    """Search the current user's indexed knowledge."""

    results = await search_service.search(
        db_session,
        user_id=current_user.id,
        query=request.query,
        top_k=request.top_k,
        project_id=request.project_id,
        document_id=request.document_id,
        source_type=request.source_type,
    )

    return SearchResponse(
        query=request.query,
        results=[
            SearchResultResponse(
                chunk_id=result.chunk_id,
                document_id=result.document_id,
                content=result.content,
                score=result.similarity,
            )
            for result in results
        ],
    )