from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.risk import Risk, RiskSource
from app.intelligence.models import RiskCandidate


class RiskService:
    async def create_from_candidate(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        candidate: RiskCandidate,
    ) -> Risk:
        source_chunk_ids = self._unique_source_chunk_ids(candidate)

        await self._validate_source_chunks(
            session,
            user_id=user_id,
            chunk_ids=source_chunk_ids,
        )

        risk = Risk(
            user_id=user_id,
            title=candidate.title,
            description=candidate.description,
            severity=candidate.severity,
        )

        session.add(risk)
        await session.flush()

        sources = [
            RiskSource(
                risk_id=risk.id,
                chunk_id=chunk_id,
            )
            for chunk_id in source_chunk_ids
        ]

        session.add_all(sources)
        await session.flush()

        return risk

    @staticmethod
    def _unique_source_chunk_ids(
        candidate: RiskCandidate,
    ) -> list[UUID]:
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
        if not chunk_ids:
            raise ValueError("Risk must contain at least one source chunk.")

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