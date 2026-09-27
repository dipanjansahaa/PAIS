from dataclasses import dataclass

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
    def __init__(self, retriever):
        self.retriever = retriever

    async def evaluate(
        self,
        session,
        cases: list[RetrievalEvaluationCase],
        k: int = 5,
    ) -> RetrievalEvaluationResult:
        if not cases:
            raise ValueError(
                "At least one evaluation case is required."
            )

        recall_scores = []
        reciprocal_ranks = []
        ndcg_scores = []

        for case in cases:
            results = await self.retriever.search(
                session=session,
                query=case.query,
                top_k=k,
            )

            retrieved_ids = [
                result.chunk_id
                for result in results
            ]

            recall_scores.append(
                recall_at_k(
                    retrieved_ids,
                    case.relevant_ids,
                    k,
                )
            )

            reciprocal_ranks.append(
                reciprocal_rank(
                    retrieved_ids,
                    case.relevant_ids,
                )
            )

            ndcg_scores.append(
                ndcg_at_k(
                    retrieved_ids,
                    case.relevance,
                    k,
                )
            )

        return RetrievalEvaluationResult(
            recall_at_k=sum(recall_scores)
            / len(recall_scores),
            mrr=sum(reciprocal_ranks)
            / len(reciprocal_ranks),
            ndcg_at_k=sum(ndcg_scores)
            / len(ndcg_scores),
        )