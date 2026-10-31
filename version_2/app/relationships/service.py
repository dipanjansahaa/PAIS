"""Application service for validated knowledge relationships."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.commitment import Commitment
from app.database.models.decision import Decision
from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.knowledge_relationship import (
    KNOWLEDGE_ENTITY_TYPES,
    KNOWLEDGE_RELATIONSHIP_TYPES,
    KnowledgeRelationship,
    KnowledgeRelationshipSource,
)
from app.database.models.memory import Memory
from app.database.models.person import Person
from app.database.models.project import Project
from app.database.models.risk import Risk
from app.database.models.task import Task

_ENTITY_MODELS = {
    "project": Project,
    "person": Person,
    "task": Task,
    "commitment": Commitment,
    "decision": Decision,
    "risk": Risk,
    "document": Document,
    "memory": Memory,
}


class RelationshipService:
    """Create, retrieve, and attach evidence to user-owned relationships.

    The service does not commit or roll back the caller's transaction. Since
    endpoint IDs are polymorphic, all endpoint existence and ownership checks
    happen here before a relationship is persisted.
    """

    async def create_relationship(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        source_type: str,
        source_id: UUID,
        relationship_type: str,
        target_type: str,
        target_id: UUID,
    ) -> KnowledgeRelationship:
        """Create a directed relationship, returning an existing duplicate."""
        self._validate_entity_type(source_type)
        self._validate_entity_type(target_type)
        self._validate_relationship_type(relationship_type)
        self._validate_uuid(user_id, "user_id")
        self._validate_uuid(source_id, "source_id")
        self._validate_uuid(target_id, "target_id")

        if source_type == target_type and source_id == target_id:
            raise ValueError("A relationship cannot reference itself.")

        await self._validate_endpoint(
            session,
            user_id=user_id,
            entity_type=source_type,
            entity_id=source_id,
        )
        await self._validate_endpoint(
            session,
            user_id=user_id,
            entity_type=target_type,
            entity_id=target_id,
        )

        existing = await session.scalar(
            select(KnowledgeRelationship).where(
                KnowledgeRelationship.user_id == user_id,
                KnowledgeRelationship.source_type == source_type,
                KnowledgeRelationship.source_id == source_id,
                KnowledgeRelationship.relationship_type == relationship_type,
                KnowledgeRelationship.target_type == target_type,
                KnowledgeRelationship.target_id == target_id,
            )
        )
        if existing is not None:
            return existing

        # The database uniqueness constraint is the concurrency-safe source of
        # truth. ON CONFLICT avoids leaving the caller's transaction in a failed
        # state when another request inserts the same directed edge concurrently.
        await session.execute(
            postgresql_insert(KnowledgeRelationship)
            .values(
                user_id=user_id,
                source_type=source_type,
                source_id=source_id,
                relationship_type=relationship_type,
                target_type=target_type,
                target_id=target_id,
            )
            .on_conflict_do_nothing(
                constraint="uq_knowledge_relationships_directed_edge"
            )
        )

        # Query the row whether this request inserted it or lost a concurrent
        # race. The edge's unique key guarantees at most one matching row.
        persisted = await session.scalar(
            select(KnowledgeRelationship).where(
                KnowledgeRelationship.user_id == user_id,
                KnowledgeRelationship.source_type == source_type,
                KnowledgeRelationship.source_id == source_id,
                KnowledgeRelationship.relationship_type == relationship_type,
                KnowledgeRelationship.target_type == target_type,
                KnowledgeRelationship.target_id == target_id,
            )
        )
        if persisted is None:
            # Defensive: a successful insert or conflict should leave this row.
            raise RuntimeError(
                "Relationship insert completed without a persisted relationship."
            )
        return persisted

    async def get_relationship(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        relationship_id: UUID,
    ) -> KnowledgeRelationship | None:
        """Get a relationship only if it belongs to the supplied user."""
        self._validate_uuid(user_id, "user_id")
        self._validate_uuid(relationship_id, "relationship_id")
        return await session.scalar(
            select(KnowledgeRelationship).where(
                KnowledgeRelationship.id == relationship_id,
                KnowledgeRelationship.user_id == user_id,
            )
        )

    async def list_for_entity(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        entity_type: str,
        entity_id: UUID,
        limit: int = 100,
    ) -> list[KnowledgeRelationship]:
        """List incoming and outgoing relationships for a user-owned entity."""
        self._validate_entity_type(entity_type)
        self._validate_uuid(user_id, "user_id")
        self._validate_uuid(entity_id, "entity_id")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100.")

        await self._validate_endpoint(
            session,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        result = await session.scalars(
            select(KnowledgeRelationship)
            .where(
                KnowledgeRelationship.user_id == user_id,
                or_(
                    (
                        (KnowledgeRelationship.source_type == entity_type)
                        & (KnowledgeRelationship.source_id == entity_id)
                    ),
                    (
                        (KnowledgeRelationship.target_type == entity_type)
                        & (KnowledgeRelationship.target_id == entity_id)
                    ),
                ),
            )
            .order_by(
                KnowledgeRelationship.created_at.desc(),
                KnowledgeRelationship.id,
            )
            .limit(limit)
        )
        return list(result.all())

    async def add_sources(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        relationship_id: UUID,
        chunk_ids: list[UUID],
    ) -> list[KnowledgeRelationshipSource]:
        """Attach validated document-chunk evidence to a relationship.

        Repeated chunk IDs and already-attached evidence are treated
        idempotently. Empty evidence lists are rejected rather than silently
        doing nothing.
        """
        self._validate_uuid(user_id, "user_id")
        self._validate_uuid(relationship_id, "relationship_id")
        unique_chunk_ids = self._unique_uuids(chunk_ids, field_name="chunk_id")
        if not unique_chunk_ids:
            raise ValueError("At least one source chunk is required.")

        relationship = await session.scalar(
            select(KnowledgeRelationship).where(
                KnowledgeRelationship.id == relationship_id,
                KnowledgeRelationship.user_id == user_id,
            )
        )
        if relationship is None:
            raise ValueError("Relationship does not belong to the user.")

        valid_result = await session.scalars(
            select(DocumentChunk.id)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                DocumentChunk.id.in_(unique_chunk_ids),
                Document.user_id == user_id,
            )
        )
        valid_chunk_ids = set(valid_result.all())
        if set(unique_chunk_ids) - valid_chunk_ids:
            raise ValueError(
                "One or more source chunks do not belong to the user."
            )

        # The composite primary key prevents duplicate provenance rows. Use
        # ON CONFLICT as well so concurrent requests attaching the same chunk
        # do not poison the caller's transaction with an IntegrityError.
        await session.execute(
            postgresql_insert(KnowledgeRelationshipSource)
            .values(
                [
                    {
                        "relationship_id": relationship_id,
                        "chunk_id": chunk_id,
                    }
                    for chunk_id in unique_chunk_ids
                ]
            )
            .on_conflict_do_nothing(
                index_elements=[
                    KnowledgeRelationshipSource.relationship_id,
                    KnowledgeRelationshipSource.chunk_id,
                ]
            )
        )

        persisted_result = await session.scalars(
            select(KnowledgeRelationshipSource).where(
                KnowledgeRelationshipSource.relationship_id == relationship_id,
                KnowledgeRelationshipSource.chunk_id.in_(unique_chunk_ids),
            )
        )
        persisted_by_chunk = {
            source.chunk_id: source for source in persisted_result.all()
        }
        # If the database did not return every requested row, fail loudly
        # rather than silently returning incomplete provenance.
        if set(persisted_by_chunk) != set(unique_chunk_ids):
            raise RuntimeError(
                "Relationship provenance insert completed without all rows persisted."
            )
        return [persisted_by_chunk[chunk_id] for chunk_id in unique_chunk_ids]

    @staticmethod
    def _validate_entity_type(entity_type: str) -> None:
        if entity_type not in KNOWLEDGE_ENTITY_TYPES:
            raise ValueError("Unsupported knowledge entity type.")

    @staticmethod
    def _validate_relationship_type(relationship_type: str) -> None:
        if relationship_type not in KNOWLEDGE_RELATIONSHIP_TYPES:
            raise ValueError("Unsupported knowledge relationship type.")

    @staticmethod
    def _validate_uuid(value: UUID, field_name: str) -> None:
        if not isinstance(value, UUID):
            raise ValueError(f"{field_name} must be a UUID.")

    @staticmethod
    async def _validate_endpoint(
        session: AsyncSession,
        *,
        user_id: UUID,
        entity_type: str,
        entity_id: UUID,
    ) -> None:
        """Require an endpoint to exist and be owned by the requesting user."""
        model = _ENTITY_MODELS[entity_type]
        result = await session.scalar(
            select(model.id).where(
                model.id == entity_id,
                model.user_id == user_id,
            )
        )
        if result is None:
            raise ValueError(
                f"{entity_type.capitalize()} does not exist or does not belong to the user."
            )

    @classmethod
    def _unique_uuids(
        cls,
        values: list[UUID],
        *,
        field_name: str,
    ) -> list[UUID]:
        """Validate UUID values and deduplicate them while preserving order."""
        seen: set[UUID] = set()
        unique_values: list[UUID] = []
        for value in values:
            cls._validate_uuid(value, field_name)
            if value not in seen:
                seen.add(value)
                unique_values.append(value)
        return unique_values
