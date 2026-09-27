from __future__ import annotations

from app.retrieval.models import RetrievalResult


class RerankedRetriever:
    """
    Wraps an existing retriever with a reranking stage.

    The base retriever produces a larger candidate set.
    The reranker then selects the final top_k results.
    """

    def __init__(
        self,
        base_retriever,
        reranking_service,
        candidate_k: int = 20,
    ) -> None:
        if candidate_k <= 0:
            raise ValueError("candidate_k must be greater than zero.")

        self.base_retriever = base_retriever
        self.reranking_service = reranking_service
        self.candidate_k = candidate_k

    async def search(
        self,
        session,
        query: str,
        top_k: int = 5,
        project_id=None,
        document_id=None,
        source_type=None,
    ) -> list[RetrievalResult]:
        if not query.strip():
            raise ValueError("Query must not be empty.")

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        candidates = await self.base_retriever.search(
            session=session,
            query=query,
            top_k=self.candidate_k,
            project_id=project_id,
            document_id=document_id,
            source_type=source_type,
        )

        return await self.reranking_service.rerank(
            query=query,
            candidates=candidates,
            top_k=top_k,
        )