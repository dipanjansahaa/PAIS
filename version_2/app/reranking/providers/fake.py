from __future__ import annotations

from app.reranking.base import Reranker
from app.retrieval.models import RetrievalResult


class FakeReranker(Reranker):
    """Deterministic reranker used for testing."""

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

        ranked = sorted(
            candidates,
            key=lambda result: result.content,
        )

        return [
            RetrievalResult(
                chunk_id=result.chunk_id,
                document_id=result.document_id,
                content=result.content,
                similarity=1.0 / (index + 1),
                metadata=result.metadata,
            )
            for index, result in enumerate(ranked[:top_k])
        ]