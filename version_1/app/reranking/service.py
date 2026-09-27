from __future__ import annotations

from app.retrieval.models import RetrievalResult
from app.reranking.base import Reranker


class RerankingService:
    """Application service for reranking retrieval candidates."""

    def __init__(self, reranker: Reranker) -> None:
        self.reranker = reranker

    async def rerank(
        self,
        query: str,
        candidates: list[RetrievalResult],
        top_k: int = 5,
    ) -> list[RetrievalResult]:
        if not query.strip():
            raise ValueError("Query must not be empty.")

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        if not candidates:
            return []

        return await self.reranker.rerank(
            query=query,
            candidates=candidates,
            top_k=top_k,
        )