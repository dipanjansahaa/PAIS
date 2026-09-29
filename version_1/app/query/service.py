"""Application service for grounded query answering."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base import LLMProvider
from app.llm.models import Message
from app.query.context import ContextBuilder
from app.query.models import QueryResult
from app.retrieval.service import SearchService


GROUNDING_SYSTEM_PROMPT = """\
You are the PAIS knowledge assistant.

Answer the user's question using only the supplied sources.

Rules:
- Use only information supported by the supplied sources.
- Do not invent facts or fill missing information with assumptions.
- If the sources do not contain enough information to answer the question,
  clearly state that the available sources are insufficient.
- When making factual claims, cite the supporting source or chunk using
  the citation IDs provided in the context.
- Keep the answer concise and directly address the user's question.
"""


class QueryService:
    """Coordinate retrieval, context construction, and generation."""

    def __init__(
        self,
        *,
        search_service: SearchService,
        context_builder: ContextBuilder,
        llm_provider: LLMProvider,
    ) -> None:
        self.search_service = search_service
        self.context_builder = context_builder
        self.llm_provider = llm_provider

    async def query(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        query: str,
        top_k: int = 5,
        project_id: UUID | None = None,
        document_id: UUID | None = None,
        source_type: str | None = None,
        temperature: float = 0.0,
    ) -> QueryResult:
        """Answer a user query using grounded retrieved context."""

        if not query.strip():
            raise ValueError("Query must not be empty.")

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        retrieval_results = await self.search_service.search(
            session,
            user_id=user_id,
            query=query,
            top_k=top_k,
            project_id=project_id,
            document_id=document_id,
            source_type=source_type,
        )

        context = self.context_builder.build(retrieval_results)

        if not context.sources:
            return QueryResult(
                query=query,
                answer=(
                    "I don't have enough information in the available "
                    "sources to answer this question."
                ),
                sources=(),
                model=None,
                latency_ms=None,
                truncated=False,
            )

        messages = self._build_messages(
            query=query,
            context=context.text,
        )

        response = await self.llm_provider.generate(
            messages,
            temperature=temperature,
        )

        return self._build_result(
            query=query,
            context=context,
            response=response,
        )

    @staticmethod
    def _build_messages(
        *,
        query: str,
        context: str,
    ) -> list[Message]:
        """Build the grounded generation prompt."""

        user_prompt = (
            "SOURCES:\n"
            f"{context}\n\n"
            "QUESTION:\n"
            f"{query}"
        )

        return [
            Message(
                role="system",
                content=GROUNDING_SYSTEM_PROMPT,
            ),
            Message(
                role="user",
                content=user_prompt,
            ),
        ]

    @staticmethod
    def _build_result(
        *,
        query: str,
        context,
        response,
    ) -> QueryResult:
        """Convert provider and context results into QueryResult."""

        return QueryResult(
            query=query,
            answer=response.content,
            sources=context.sources,
            model=response.model,
            latency_ms=response.latency_ms,
            truncated=context.truncated,
        )