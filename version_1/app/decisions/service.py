"""Application service for decision persistence."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.decision import Decision, DecisionSource
from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.project import Project
from app.intelligence.models import DecisionCandidate


class DecisionService:
    """Create and manage persisted decisions."""

    async def create_from_candidate(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        candidate: DecisionCandidate,
        project_id: UUID | None = None,
    ) -> Decision:
        """Persist a decision candidate together with its provenance."""

        await self._validate_project(
            session,
            user_id=user_id,
            project_id=project_id,
        )

        source_chunk_ids = self._unique_source_chunk_ids(candidate)

        await self._validate_source_chunks(
            session,
            user_id=user_id,
            chunk_ids=source_chunk_ids,
        )

        decision = Decision(
            user_id=user_id,
            project_id=project_id,
            title=candidate.title,
            description=candidate.description,
            decision_date=candidate.decision_date,
        )

        session.add(decision)

        await session.flush()

        sources = [
            DecisionSource(
                decision_id=decision.id,
                chunk_id=chunk_id,
            )
            for chunk_id in source_chunk_ids
        ]

        session.add_all(sources)

        await session.flush()

        return decision

    @staticmethod
    def _unique_source_chunk_ids(
        candidate: DecisionCandidate,
    ) -> list[UUID]:
        """Return source chunk IDs without duplicates, preserving order."""

        seen: set[UUID] = set()
        chunk_ids: list[UUID] = []

        for source in candidate.sources:
            if source.chunk_id not in seen:
                seen.add(source.chunk_id)
                chunk_ids.append(source.chunk_id)

        return chunk_ids

    @staticmethod
    async def _validate_project(
        session: AsyncSession,
        *,
        user_id: UUID,
        project_id: UUID | None,
    ) -> None:
        """Ensure the project belongs to the requesting user."""

        if project_id is None:
            return

        result = await session.scalar(
            select(Project.id).where(
                Project.id == project_id,
                Project.user_id == user_id,
            )
        )

        if result is None:
            raise ValueError("Project does not belong to the user.")

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
                "Decision must contain at least one source chunk."
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