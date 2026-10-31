"""Evaluation utilities for relationship-aware query context."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.evaluation.cases import RelationshipEvaluationCase
from app.evaluation.retrieval import (
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)
from app.evaluation.runner import RetrievalEvaluationResult
from app.query.relationship_context import RelationshipContextBuilder
from sqlalchemy.ext.asyncio import AsyncSession


class RelationshipContextEvaluator:
    """Evaluate relationship retrieval against labelled seed-entity cases.

    This measures relationships returned by the existing context builder. It
    does not evaluate LLM answer quality, infer entities from free text, or
    claim complete historical reconstruction.
    """

    def __init__(
        self,
        context_builder: RelationshipContextBuilder | None = None,
    ) -> None:
        self.context_builder = context_builder or RelationshipContextBuilder()

    async def evaluate(
        self,
        session: AsyncSession,
        cases: list[RelationshipEvaluationCase],
        *,
        user_id: UUID,
        k: int = 5,
        as_of: datetime,
    ) -> RetrievalEvaluationResult:
        """Calculate mean Recall@K, MRR, and NDCG@K for relationship results."""
        if not cases:
            raise ValueError("At least one evaluation case is required.")
        if not 1 <= k <= 100:
            raise ValueError("k must be between 1 and 100.")
        if not isinstance(as_of, datetime) or as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be a timezone-aware datetime.")

        recall_scores: list[float] = []
        reciprocal_ranks: list[float] = []
        ndcg_scores: list[float] = []

        for case in cases:
            context = await self.context_builder.build(
                session,
                user_id=user_id,
                entity_type=case.entity_type,
                entity_id=case.entity_id,
                limit=k,
                as_of=as_of,
            )
            retrieved_ids = [UUID(item.relationship_id) for item in context.relationships]

            recall_scores.append(recall_at_k(retrieved_ids, case.relevant_ids, k))
            reciprocal_ranks.append(reciprocal_rank(retrieved_ids, case.relevant_ids))
            ndcg_scores.append(ndcg_at_k(retrieved_ids, case.relevance, k))

        case_count = len(cases)
        return RetrievalEvaluationResult(
            recall_at_k=sum(recall_scores) / case_count,
            mrr=sum(reciprocal_ranks) / case_count,
            ndcg_at_k=sum(ndcg_scores) / case_count,
        )
