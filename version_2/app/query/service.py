"""Application service for grounded query answering."""

from __future__ import annotations

from datetime import datetime
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
from app.query.relationship_context import (
    QueryRelationship,
    RelationshipContextBuilder,
)
from app.retrieval.service import SearchService


class QueryEntityNotFoundError(ValueError):
    """Raised when an explicit query seed entity is unavailable to the user."""


GROUNDING_SYSTEM_PROMPT = """\
You are the PAIS knowledge assistant.

Answer the user's question using only the supplied sources and personal memories.

The evidence may contain three distinct kinds of information:
1. DOCUMENT SOURCES: Retrieved document chunks with citation IDs.
2. PERSONAL MEMORIES: Saved information about the authenticated user,
   with memory reference IDs.
3. KNOWLEDGE RELATIONSHIPS: Stored directed links between user-owned entities,
   optionally supported by document chunk provenance.

Rules:
- Use only information supported by the supplied evidence.
- Do not invent facts or fill missing information with assumptions.
- Treat personal memories as contextual information, not as document text.
- A memory's status describes its current stored lifecycle, not its historical
  status at the requested as_of instant. Use stored validity boundaries for
  temporal applicability; do not infer a historical transition from status.
- A null validity boundary is unknown, not proof of indefinite validity. If
  either boundary is missing, qualify any temporal conclusion accordingly.
- Do not imply a personal memory came from a document unless the supplied
  provenance explicitly supports that claim.
- Cite document-based factual claims using the provided document chunk IDs,
  such as [S1-C1].
- When a claim relies on a personal memory, cite its memory ID, such as [M1].
- When a claim relies on a stored relationship, cite its relationship ID, such as [R1].
- Relationship provenance chunks use identifiers such as [R1-C1]; do not imply
  provenance exists when no source chunk is supplied.
- You may cite multiple evidence types when they jointly support a claim.
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
        relationship_context_builder: RelationshipContextBuilder | None = None,
    ) -> None:
        self.search_service = search_service
        self.context_builder = context_builder
        self.llm_provider = llm_provider
        self.memory_service = memory_service
        self.relationship_context_builder = (
            relationship_context_builder or RelationshipContextBuilder()
        )

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
        as_of: datetime | None = None,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
    ) -> QueryResult:
        """Answer a query using document evidence and personal memory."""

        if not query.strip():
            raise ValueError("Query must not be empty.")

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")
        if as_of is not None and (
            not isinstance(as_of, datetime) or as_of.tzinfo is None or as_of.utcoffset() is None
        ):
            raise ValueError("as_of must be a timezone-aware datetime.")

        if (entity_type is None) != (entity_id is None):
            raise ValueError("entity_type and entity_id must be provided together.")

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

        relationship_context = None
        relationships: tuple[QueryRelationship, ...] = ()
        if entity_type is not None and entity_id is not None:
            try:
                relationship_context = await self.relationship_context_builder.build(
                    session,
                    user_id=user_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    limit=20,
                    as_of=as_of,
                )
            except ValueError as exc:
                if "does not exist or does not belong" in str(exc):
                    raise QueryEntityNotFoundError(
                        "Entity does not exist or does not belong to the user."
                    ) from exc
                raise
            relationships = relationship_context.relationships

        # Memory retrieval is scoped to the authenticated user. Current-state
        # queries use active status; explicit as_of queries use stored valid time.
        memories: tuple[QueryMemory, ...] = ()

        if self.memory_service is not None:
            retrieved_memories = await self.memory_service.retrieve_memories(
                session,
                user_id=user_id,
                query=query,
                limit=10,
                as_of=as_of,
            )

            memories = tuple(
                QueryMemory(
                    citation_id=f"M{index}",
                    memory_id=str(memory.id),
                    memory_type=memory.memory_type,
                    content=memory.content,
                    status=memory.status,
                    valid_from=memory.valid_from,
                    valid_until=memory.valid_until,
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
        if not document_context.sources and not memories and not relationships:
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
                relationships=(),
            )

        messages = self._build_messages(
            query=query,
            document_context=document_context.text,
            memories=memories,
            relationship_context=(relationship_context.text if relationship_context else ""),
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
            relationships=relationships,
        )

    @staticmethod
    def _build_messages(
        *,
        query: str,
        document_context: str,
        memories: tuple[QueryMemory, ...] = (),
        relationship_context: str = "",
    ) -> list[Message]:
        """Build a prompt with distinct document and memory evidence."""

        memory_sections = []
        for memory in memories:
            validity_note = ""
            if memory.valid_from is None or memory.valid_until is None:
                validity_note = (
                    "\nTemporal note: one or both validity boundaries are unknown; "
                    "do not assume indefinite validity."
                )
            memory_sections.append(
                f"[{memory.citation_id}]\n"
                f"Type: {memory.memory_type}\n"
                f"Current stored status: {memory.status}\n"
                f"Valid from: "
                f"{memory.valid_from.isoformat() if memory.valid_from else 'unknown'}\n"
                f"Valid until: "
                f"{memory.valid_until.isoformat() if memory.valid_until else 'unknown'}\n"
                f"Content: {memory.content}"
                f"{validity_note}"
            )

        memory_context = (
            "\n\n".join(memory_sections)
            if memory_sections
            else "(No relevant personal memories retrieved.)"
        )

        relationship_text = relationship_context or (
            "(No relationship context requested or retrieved.)"
        )
        user_prompt = (
            "DOCUMENT SOURCES:\n"
            f"{document_context or '(No relevant document sources retrieved.)'}"
            "\n\n"
            "PERSONAL MEMORIES:\n"
            f"{memory_context}\n\n"
            "KNOWLEDGE RELATIONSHIPS:\n"
            f"{relationship_text}\n\n"
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
