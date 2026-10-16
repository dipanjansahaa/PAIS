from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.person import Person, PersonSource
from app.intelligence.models import PersonCandidate


class PersonService:
    """Create and manage persisted people."""

    async def create_from_candidate(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        candidate: PersonCandidate,
    ) -> Person:
        """Persist a person candidate together with its provenance."""

        source_chunk_ids = self._unique_source_chunk_ids(candidate)

        await self._validate_source_chunks(
            session,
            user_id=user_id,
            chunk_ids=source_chunk_ids,
        )

        person = Person(
            user_id=user_id,
            name=candidate.name,
            email=candidate.email,
        )

        session.add(person)

        await session.flush()

        sources = [
            PersonSource(
                person_id=person.id,
                chunk_id=chunk_id,
            )
            for chunk_id in source_chunk_ids
        ]

        session.add_all(sources)

        await session.flush()

        return person

    @staticmethod
    def _unique_source_chunk_ids(
        candidate: PersonCandidate,
    ) -> list[UUID]:
        """Return source chunk IDs without duplicates."""

        seen: set[UUID] = set()
        chunk_ids: list[UUID] = []

        for source in candidate.sources:
            if source.chunk_id in seen:
                continue

            seen.add(source.chunk_id)
            chunk_ids.append(source.chunk_id)

        return chunk_ids

    @staticmethod
    async def _validate_source_chunks(
        session: AsyncSession,
        *,
        user_id: UUID,
        chunk_ids: list[UUID],
    ) -> None:
        """Ensure all provenance chunks belong to the requesting user."""

        if not chunk_ids:
            raise ValueError(
                "Person must contain at least one source chunk."
            )

        result = await session.scalars(
            select(DocumentChunk.id)
            .join(
                Document,
                Document.id == DocumentChunk.document_id,
            )
            .where(
                DocumentChunk.id.in_(chunk_ids),
                Document.user_id == user_id,
            )
        )

        valid_chunk_ids = set(result.all())

        missing_chunk_ids = set(chunk_ids) - valid_chunk_ids

        if missing_chunk_ids:
            raise ValueError(
                "One or more source chunks do not belong to the user."
            )