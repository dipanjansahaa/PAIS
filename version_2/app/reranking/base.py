from __future__ import annotations

from abc import ABC, abstractmethod

from app.retrieval.models import RetrievalResult


class Reranker(ABC):
    """Provider-agnostic interface for reranking retrieved candidates."""

    @abstractmethod
    async def rerank(
        self,
        query: str,
        candidates: list[RetrievalResult],
        top_k: int = 5,
    ) -> list[RetrievalResult]:
        """Rerank retrieval candidates for the given query."""
        raise NotImplementedError