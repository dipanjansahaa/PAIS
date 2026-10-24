"""Application service for grounded query answering."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base import LLMProvider
from app.llm.models import Message
from app.memory.service import MemoryService
from app.query.context import ContextBuilder
from app.query.models import (
    QueryMemory,
    QueryMemorySource,
    QueryResult,
)
from app.retrieval.service import SearchService

GROUNDING_SYSTEM_PROMPT = """\
You are the PAIS knowledge assistant.

Answer the user's question using only the supplied sources and personal memories.

The evidence may contain two distinct kinds of information:
1. DOCUMENT SOURCES: Retrieved document chunks with citation IDs.
2. PERSONAL MEMORIES: Saved information about the authenticated user,
   with memory reference IDs.

Rules:
- Use only information supported by the supplied evidence.
- Do not invent facts or fill missing information with assumptions.
- Treat personal memories as contextual information, not as document text.
- Do not imply a personal memory came from a document unless the supplied
  provenance explicitly supports that claim.
- Cite document-based factual claims using the provided document chunk IDs,
  such as [S1-C1].
- When a claim relies on a personal memory, cite its memory ID, such as [M1].
- You may cite both kinds of evidence when both support a claim.
- If the evidence does not contain enough information, clearly state that.
- Keep the answer concise and directly address the question.
"""


class QueryService:
    """Coordinate retrieval, context construction, and generation."""

    def __init__(
        self,
        *,
        search_service: SearchService,
        context_builder: ContextBuilder,
        llm_provider: LLMProvider,
        memory_service: MemoryService | None = None,
    ) -> None:
        self.search_service = search_service
        self.context_builder = context_builder
        self.llm_provider = llm_provider
        self.memory_service = memory_service

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
        """Answer a query using document evidence and personal memory."""

        if not query.strip():
            raise ValueError("Query must not be empty.")

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        # Keep existing document retrieval and its filters unchanged.
        retrieval_results = await self.search_service.search(
            session,
            user_id=user_id,
            query=query,
            top_k=top_k,
            project_id=project_id,
            document_id=document_id,
            source_type=source_type,
        )

        document_context = self.context_builder.build(retrieval_results)

        # Memory retrieval is scoped to the authenticated user and
        # independently respects active status and validity windows.
        memories: tuple[QueryMemory, ...] = ()

        if self.memory_service is not None:
            retrieved_memories = await self.memory_service.retrieve_memories(
                session,
                user_id=user_id,
                query=query,
                limit=10,
            )

            memories = tuple(
                QueryMemory(
                    citation_id=f"M{index}",
                    memory_id=str(memory.id),
                    memory_type=memory.memory_type,
                    content=memory.content,
                    confidence=memory.confidence,
                    sources=tuple(
                        QueryMemorySource(
                            source_kind=source.source_kind,
                            document_id=(
                                str(source.document_id) if source.document_id is not None else None
                            ),
                            chunk_id=(
                                str(source.chunk_id) if source.chunk_id is not None else None
                            ),
                            source_reference=source.source_reference,
                            evidence_text=source.evidence_text,
                        )
                        for source in memory.sources
                    ),
                )
                for index, memory in enumerate(
                    retrieved_memories,
                    start=1,
                )
            )

        # Do not call the LLM without any supporting evidence.
        if not document_context.sources and not memories:
            return QueryResult(
                query=query,
                answer=(
                    "I don't have enough information in the available sources "
                    "to answer this question."
                ),
                sources=(),
                model=None,
                latency_ms=None,
                truncated=False,
                memories=(),
            )

        messages = self._build_messages(
            query=query,
            document_context=document_context.text,
            memories=memories,
        )

        response = await self.llm_provider.generate(
            messages,
            temperature=temperature,
        )

        return QueryResult(
            query=query,
            answer=response.content,
            sources=document_context.sources,
            model=response.model,
            latency_ms=response.latency_ms,
            truncated=document_context.truncated,
            memories=memories,
        )

    @staticmethod
    def _build_messages(
        *,
        query: str,
        document_context: str,
        memories: tuple[QueryMemory, ...] = (),
    ) -> list[Message]:
        """Build a prompt with distinct document and memory evidence."""

        memory_sections = [
            (f"[{memory.citation_id}]\nType: {memory.memory_type}\nContent: {memory.content}")
            for memory in memories
        ]

        memory_context = (
            "\n\n".join(memory_sections)
            if memory_sections
            else "(No relevant personal memories retrieved.)"
        )

        user_prompt = (
            "DOCUMENT SOURCES:\n"
            f"{document_context or '(No relevant document sources retrieved.)'}"
            "\n\n"
            "PERSONAL MEMORIES:\n"
            f"{memory_context}\n\n"
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
