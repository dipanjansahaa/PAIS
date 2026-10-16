"""Application service for search operations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.models import RetrievalResult


class SearchService:
    """Coordinate search requests through a configured retriever."""

    def __init__(self, retriever) -> None:
        self.retriever = retriever

    async def search(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        query: str,
        top_k: int = 5,
        project_id: UUID | None = None,
        document_id: UUID | None = None,
        source_type: str | None = None,
    ) -> list[RetrievalResult]:
        """Search indexed document chunks."""

        if not query.strip():
            raise ValueError("Query must not be empty.")

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        return await self.retriever.search(
            session=session,
            user_id=user_id,
            query=query,
            top_k=top_k,
            project_id=project_id,
            document_id=document_id,
            source_type=source_type,
        )