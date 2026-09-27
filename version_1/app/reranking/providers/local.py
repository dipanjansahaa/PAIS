from __future__ import annotations

from sentence_transformers import CrossEncoder

from app.core.config import settings
from app.retrieval.models import RetrievalResult
from app.reranking.base import Reranker


class LocalCrossEncoderReranker(Reranker):
    """Local cross-encoder implementation of the Reranker interface."""

    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
        batch_size: int | None = None,
    ) -> None:
        self.model_name = model_name or settings.reranker_model
        self.device = device or settings.reranker_device
        self.batch_size = batch_size or settings.reranker_batch_size

        if self.batch_size <= 0:
            raise ValueError("batch_size must be greater than zero.")

        self.model = CrossEncoder(
            self.model_name,
            device=self.device,
        )

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

        pairs = [
            [query, candidate.content]
            for candidate in candidates
        ]

        scores = self.model.predict(
            pairs,
            batch_size=self.batch_size,
            show_progress_bar=False,
        )

        scored_candidates = [
            (candidate, float(score))
            for candidate, score in zip(candidates, scores, strict=True)
        ]

        scored_candidates.sort(
            key=lambda item: (
                -item[1],
                str(item[0].chunk_id),
            )
        )

        return [
            RetrievalResult(
                chunk_id=candidate.chunk_id,
                document_id=candidate.document_id,
                content=candidate.content,
                similarity=score,
                metadata=candidate.metadata,
            )
            for candidate, score in scored_candidates[:top_k]
        ]