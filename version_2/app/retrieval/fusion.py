from uuid import UUID

from app.retrieval.models import RetrievalResult


class RRFFusion:
    """
    Reciprocal Rank Fusion for combining ranked retrieval results.

    RRF score:

        score = sum(1 / (k + rank))

    Rank starts at 1.
    """

    def __init__(self, k: int = 60):
        if k <= 0:
            raise ValueError("RRF k must be greater than zero.")

        self.k = k

    def fuse(
        self,
        result_lists: list[list[RetrievalResult]],
        top_k: int = 5,
    ) -> list[RetrievalResult]:
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        scores: dict[UUID, float] = {}
        results_by_chunk: dict[UUID, RetrievalResult] = {}

        for results in result_lists:
            seen_in_list: set[UUID] = set()

            for rank, result in enumerate(results, start=1):
                if result.chunk_id in seen_in_list:
                    continue

                seen_in_list.add(result.chunk_id)

                scores[result.chunk_id] = (
                    scores.get(result.chunk_id, 0.0)
                    + 1.0 / (self.k + rank)
                )

                results_by_chunk.setdefault(
                    result.chunk_id,
                    result,
                )

        ranked_results = sorted(
            scores.items(),
            key=lambda item: (-item[1], str(item[0])),
        )

        fused_results = []

        for chunk_id, score in ranked_results[:top_k]:
            result = results_by_chunk[chunk_id]

            fused_results.append(
                RetrievalResult(
                    chunk_id=result.chunk_id,
                    document_id=result.document_id,
                    content=result.content,
                    similarity=score,
                    metadata=result.metadata,
                )
            )

        return fused_results