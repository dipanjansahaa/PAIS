"""Shared evaluation runner for document retrieval benchmarks."""

from dataclasses import dataclass
from uuid import UUID

from app.evaluation.cases import RetrievalEvaluationCase
from app.evaluation.retrieval import (
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)


@dataclass(frozen=True)
class RetrievalEvaluationResult:
    recall_at_k: float
    mrr: float
    ndcg_at_k: float


class RetrievalEvaluator:
    """Evaluate a retriever against explicitly labelled query cases."""

    def __init__(self, retriever) -> None:
        self.retriever = retriever

    async def evaluate(
        self,
        session,
        cases: list[RetrievalEvaluationCase],
        *,
        user_id: UUID,
        k: int = 5,
    ) -> RetrievalEvaluationResult:
        """Return macro-averaged Recall@K, MRR, and NDCG@K.

        Input validation is performed before querying the retriever so an
        invalid benchmark configuration fails deterministically without
        issuing retrieval calls.
        """
        if not cases:
            raise ValueError("At least one evaluation case is required.")
        if not 1 <= k <= 100:
            raise ValueError("k must be between 1 and 100.")

        recall_scores: list[float] = []
        reciprocal_ranks: list[float] = []
        ndcg_scores: list[float] = []

        for case in cases:
            results = await self.retriever.search(
                session=session,
                query=case.query,
                top_k=k,
                user_id=user_id,
            )
            retrieved_ids = [result.chunk_id for result in results]

            recall_scores.append(
                recall_at_k(retrieved_ids, case.relevant_ids, k)
            )
            reciprocal_ranks.append(
                reciprocal_rank(retrieved_ids, case.relevant_ids)
            )
            ndcg_scores.append(
                ndcg_at_k(retrieved_ids, case.relevance, k)
            )

        case_count = len(cases)
        return RetrievalEvaluationResult(
            recall_at_k=sum(recall_scores) / case_count,
            mrr=sum(reciprocal_ranks) / case_count,
            ndcg_at_k=sum(ndcg_scores) / case_count,
        )
