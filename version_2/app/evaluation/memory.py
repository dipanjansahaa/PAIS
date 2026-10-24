"""Evaluation utilities for personal-memory retrieval."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.evaluation.cases import MemoryEvaluationCase
from app.evaluation.retrieval import (
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)
from app.evaluation.runner import RetrievalEvaluationResult
from app.memory.service import MemoryService
from sqlalchemy.ext.asyncio import AsyncSession


class MemoryRetrievalEvaluator:
    """Evaluate personal-memory retrieval against labelled query cases."""

    def __init__(self, memory_service: MemoryService) -> None:
        self.memory_service = memory_service

    async def evaluate(
        self,
        session: AsyncSession,
        cases: list[MemoryEvaluationCase],
        *,
        user_id: UUID,
        k: int = 5,
        as_of: datetime | None = None,
    ) -> RetrievalEvaluationResult:
        """Calculate mean Recall@K, MRR, and NDCG@K.

        The memory service remains responsible for user isolation,
        lifecycle filtering, validity windows, and result ranking.

        This evaluator measures the returned rankings without modifying
        memory records or managing the database transaction.
        """
        if not cases:
            raise ValueError("At least one evaluation case is required.")

        if not 1 <= k <= 100:
            raise ValueError("k must be between 1 and 100.")

        recall_scores: list[float] = []
        reciprocal_ranks: list[float] = []
        ndcg_scores: list[float] = []

        for case in cases:
            memories = await self.memory_service.retrieve_memories(
                session,
                user_id=user_id,
                query=case.query,
                limit=k,
                as_of=as_of,
            )

            retrieved_ids = [memory.id for memory in memories]

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

        case_count = len(cases)

        return RetrievalEvaluationResult(
            recall_at_k=sum(recall_scores) / case_count,
            mrr=sum(reciprocal_ranks) / case_count,
            ndcg_at_k=sum(ndcg_scores) / case_count,
        )
