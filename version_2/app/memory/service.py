"""Application service for persistent personal memory."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.memory import Memory, MemorySource

MemoryType = Literal["fact", "preference", "goal", "constraint"]


class MemoryService:
    """Create and manage persisted memories for individual users."""

    ALLOWED_MEMORY_TYPES = frozenset({"fact", "preference", "goal", "constraint"})

    def normalize_content(self, content: str) -> str:
        """Normalize content for conservative duplicate detection."""

        return re.sub(r"\s+", " ", content).strip().casefold()

    async def retrieve_memories(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        query: str | None = None,
        memory_types: set[MemoryType] | None = None,
        limit: int = 10,
        as_of: datetime | None = None,
    ) -> list[Memory]:
        """Retrieve currently valid memories relevant to a query.

        Retrieval is always scoped to the supplied user. Only active
        memories whose validity window includes ``as_of`` are returned.

        When a query is supplied, results are ranked by lexical relevance,
        confidence, and recency. Without a query, results are ordered by
        recency and confidence.

        The caller owns the transaction. This method does not commit
        or mutate memory lifecycle state.
        """
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100.")

        if memory_types is not None:
            invalid_types = memory_types - self.ALLOWED_MEMORY_TYPES
            if invalid_types:
                raise ValueError("Unsupported memory type.")

        now = as_of or datetime.now(UTC)

        statement = (
            select(Memory)
            .options(selectinload(Memory.sources))
            .where(
                Memory.user_id == user_id,
                Memory.status == "active",
                or_(
                    Memory.valid_from.is_(None),
                    Memory.valid_from <= now,
                ),
                or_(
                    Memory.valid_until.is_(None),
                    Memory.valid_until > now,
                ),
            )
        )

        if memory_types:
            statement = statement.where(Memory.memory_type.in_(memory_types))

        result = await session.scalars(statement)
        memories = list(result.all())

        normalized_query = self.normalize_content(query or "")
        query_terms = set(re.findall(r"\b\w+\b", normalized_query))

        if not query_terms:
            memories.sort(
                key=lambda memory: (
                    memory.created_at,
                    memory.confidence if memory.confidence is not None else -1.0,
                    str(memory.id),
                ),
                reverse=True,
            )
            return memories[:limit]

        def relevance_key(memory: Memory) -> tuple[float, float, datetime, str]:
            normalized_content = self.normalize_content(memory.content)
            content_terms = set(re.findall(r"\b\w+\b", normalized_content))

            overlap = len(query_terms & content_terms) / len(query_terms)
            phrase_match = 1.0 if normalized_query in normalized_content else 0.0

            score = overlap + phrase_match

            confidence = memory.confidence if memory.confidence is not None else -1.0

            return (
                score,
                confidence,
                memory.created_at,
                str(memory.id),
            )

        memories.sort(key=relevance_key, reverse=True)

        # A zero-overlap result is not relevant enough to return.
        relevant_memories = [memory for memory in memories if relevance_key(memory)[0] > 0.0]

        return relevant_memories[:limit]

    async def create_memory(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        memory_type: MemoryType,
        content: str,
        confidence: float | None = None,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
        source_kind: str = "manual",
        document_id: UUID | None = None,
        chunk_id: UUID | None = None,
        source_reference: str | None = None,
        evidence_text: str | None = None,
    ) -> Memory:
        """Create a memory, or refresh an equivalent active memory.

        The caller owns the transaction and is responsible for committing
        or rolling back the session.
        """

        normalized_content = self.normalize_content(content)

        if not normalized_content:
            raise ValueError("Memory content must not be empty.")

        if memory_type not in self.ALLOWED_MEMORY_TYPES:
            raise ValueError("Unsupported memory type.")

        if confidence is not None and not 0.0 <= confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0.")

        if valid_from is not None and valid_until is not None and valid_until <= valid_from:
            raise ValueError("valid_until must be later than valid_from.")

        await self._validate_sources(
            session,
            user_id=user_id,
            document_id=document_id,
            chunk_id=chunk_id,
        )

        now = datetime.now(UTC)

        existing = await session.scalar(
            select(Memory)
            .where(
                Memory.user_id == user_id,
                Memory.memory_type == memory_type,
                Memory.normalized_content == normalized_content,
                Memory.status == "active",
            )
            .order_by(Memory.created_at.desc())
            .limit(1)
        )

        if existing is not None:
            existing.last_confirmed_at = now

            # Keep the existing memory's content and validity unchanged.
            # New evidence is recorded as an additional provenance source.
            has_provenance = any(
                (
                    document_id is not None,
                    chunk_id is not None,
                    source_reference is not None,
                    evidence_text is not None,
                    source_kind != "manual",
                )
            )

            if has_provenance:
                source = MemorySource(
                    memory_id=existing.id,
                    source_kind=source_kind,
                    document_id=document_id,
                    chunk_id=chunk_id,
                    source_reference=source_reference,
                    evidence_text=evidence_text,
                )
                session.add(source)

            await session.flush()
            return existing

        memory = Memory(
            user_id=user_id,
            memory_type=memory_type,
            content=content.strip(),
            normalized_content=normalized_content,
            confidence=confidence,
            valid_from=valid_from,
            valid_until=valid_until,
            last_confirmed_at=now,
        )

        session.add(memory)
        await session.flush()

        source = MemorySource(
            memory_id=memory.id,
            source_kind=source_kind,
            document_id=document_id,
            chunk_id=chunk_id,
            source_reference=source_reference,
            evidence_text=evidence_text,
        )
        session.add(source)

        await session.flush()
        return memory

    @staticmethod
    async def _validate_sources(
        session: AsyncSession,
        *,
        user_id: UUID,
        document_id: UUID | None,
        chunk_id: UUID | None,
    ) -> None:
        """Ensure provided document and chunk sources belong to the user."""

        if document_id is not None:
            valid_document_id = await session.scalar(
                select(Document.id).where(
                    Document.id == document_id,
                    Document.user_id == user_id,
                )
            )

            if valid_document_id is None:
                raise ValueError("Source document does not belong to the user.")

        if chunk_id is not None:
            valid_chunk = await session.execute(
                select(DocumentChunk.id)
                .join(
                    Document,
                    Document.id == DocumentChunk.document_id,
                )
                .where(
                    DocumentChunk.id == chunk_id,
                    Document.user_id == user_id,
                )
            )

            if valid_chunk.scalar_one_or_none() is None:
                raise ValueError("Source chunk does not belong to the user.")

            # If both IDs are supplied, they must refer to the same document.
            if document_id is not None:
                chunk_document_id = await session.scalar(
                    select(DocumentChunk.document_id).where(DocumentChunk.id == chunk_id)
                )

                if chunk_document_id != document_id:
                    raise ValueError("Source chunk does not belong to the source document.")

    async def supersede_memory(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        old_memory_id: UUID,
        replacement_memory_id: UUID,
    ) -> Memory:
        """Mark an active memory as superseded by another active memory.

        Both memories must belong to the same user. The replacement memory
        records the ID of the memory it supersedes.

        The caller owns the transaction and is responsible for committing
        or rolling back the session.
        """
        if old_memory_id == replacement_memory_id:
            raise ValueError("A memory cannot supersede itself.")

        old_memory = await session.scalar(
            select(Memory).where(
                Memory.id == old_memory_id,
                Memory.user_id == user_id,
            )
        )
        if old_memory is None:
            raise ValueError("The memory to supersede was not found.")

        replacement = await session.scalar(
            select(Memory).where(
                Memory.id == replacement_memory_id,
                Memory.user_id == user_id,
            )
        )
        if replacement is None:
            raise ValueError("The replacement memory was not found.")

        if old_memory.status != "active":
            raise ValueError("Only active memories can be superseded.")

        if replacement.status != "active":
            raise ValueError("The replacement memory must be active.")

        if old_memory.memory_type != replacement.memory_type:
            raise ValueError("A memory can only be superseded by a memory of the same type.")

        old_memory.status = "superseded"
        replacement.supersedes_id = old_memory.id

        await session.flush()
        return replacement

    async def update_memory(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        memory_id: UUID,
        content: str,
        confidence: float | None = None,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
        source_kind: str = "manual_update",
        document_id: UUID | None = None,
        chunk_id: UUID | None = None,
        source_reference: str | None = None,
        evidence_text: str | None = None,
    ) -> Memory:
        """Replace an active memory while retaining its history and provenance.

        The previous record is marked ``superseded`` and remains persisted;
        the replacement points to it through ``supersedes_id``. The caller
        owns the transaction and must commit or roll back the session.
        """
        normalized_content = self.normalize_content(content)
        if not normalized_content:
            raise ValueError("Memory content must not be empty.")
        if confidence is not None and not 0.0 <= confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0.")
        if valid_from is not None and valid_until is not None and valid_until <= valid_from:
            raise ValueError("valid_until must be later than valid_from.")

        old_memory = await session.scalar(
            select(Memory).where(
                Memory.id == memory_id,
                Memory.user_id == user_id,
            )
        )
        if old_memory is None:
            raise ValueError("The memory to update was not found.")
        if old_memory.status != "active":
            raise ValueError("Only active memories can be updated.")

        duplicate = await session.scalar(
            select(Memory).where(
                Memory.user_id == user_id,
                Memory.memory_type == old_memory.memory_type,
                Memory.normalized_content == normalized_content,
                Memory.status == "active",
                Memory.id != old_memory.id,
            )
        )
        if duplicate is not None:
            raise ValueError("An equivalent active memory already exists; resolve it explicitly.")

        await self._validate_sources(
            session,
            user_id=user_id,
            document_id=document_id,
            chunk_id=chunk_id,
        )

        replacement = Memory(
            user_id=user_id,
            memory_type=old_memory.memory_type,
            content=content.strip(),
            normalized_content=normalized_content,
            confidence=(confidence if confidence is not None else old_memory.confidence),
            valid_from=(valid_from if valid_from is not None else old_memory.valid_from),
            valid_until=(valid_until if valid_until is not None else old_memory.valid_until),
            last_confirmed_at=datetime.now(UTC),
            supersedes_id=old_memory.id,
        )
        session.add(replacement)
        await session.flush()

        source = MemorySource(
            memory_id=replacement.id,
            source_kind=source_kind,
            document_id=document_id,
            chunk_id=chunk_id,
            source_reference=source_reference,
            evidence_text=evidence_text,
        )
        session.add(source)
        old_memory.status = "superseded"
        await session.flush()
        return replacement

    async def resolve_contradiction(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        outdated_memory_id: UUID,
        accepted_memory_id: UUID,
    ) -> Memory:
        """Resolve a known contradiction using an explicit caller decision.

        This deliberately does not infer contradictions from text. The caller
        must identify the outdated and accepted records; normal ownership,
        status, and type checks are applied by ``supersede_memory``.
        """
        return await self.supersede_memory(
            session,
            user_id=user_id,
            old_memory_id=outdated_memory_id,
            replacement_memory_id=accepted_memory_id,
        )

    async def expire_outdated_memories(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        as_of: datetime | None = None,
    ) -> int:
        """Expire active memories whose validity period has ended.

        Args:
            session: Database session.
            user_id: Owner whose memories should be checked.
            as_of: Time used to evaluate expiration. Defaults to current UTC.

        Returns:
            Number of memories marked as expired.

        The caller owns the transaction and is responsible for committing
        or rolling back the session.
        """
        now = as_of or datetime.now(UTC)

        result = await session.scalars(
            select(Memory).where(
                Memory.user_id == user_id,
                Memory.status == "active",
                Memory.valid_until.is_not(None),
                Memory.valid_until <= now,
            )
        )
        expired_memories = result.all()

        for memory in expired_memories:
            memory.status = "expired"

        if expired_memories:
            await session.flush()

        return len(expired_memories)
