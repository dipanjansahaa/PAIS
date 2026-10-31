"""Application service for validated knowledge relationships."""

from __future__ import annotations

from datetime import datetime
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
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
    ) -> KnowledgeRelationship:
        """Create a directed relationship, returning an existing duplicate."""
        self._validate_entity_type(source_type)
        self._validate_entity_type(target_type)
        self._validate_relationship_type(relationship_type)
        self._validate_uuid(user_id, "user_id")
        self._validate_uuid(source_id, "source_id")
        self._validate_uuid(target_id, "target_id")
        self._validate_validity_interval(valid_from, valid_until)

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
            if valid_from is not None or valid_until is not None:
                if existing.valid_from != valid_from or existing.valid_until != valid_until:
                    raise ValueError(
                        "Relationship already exists with a different validity interval; "
                        "updating relationship validity is not supported."
                    )

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
                valid_from=valid_from,
                valid_until=valid_until,
            )
            .on_conflict_do_nothing(constraint="uq_knowledge_relationships_directed_edge")
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
            raise RuntimeError("Relationship insert completed without a persisted relationship.")
        if valid_from is not None or valid_until is not None:
            if persisted.valid_from != valid_from or persisted.valid_until != valid_until:
                raise ValueError(
                    "Relationship already exists with a different validity interval; "
                    "updating relationship validity is not supported."
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
        as_of: datetime | None = None,
    ) -> list[KnowledgeRelationship]:
        """List a user's incoming and outgoing relationships.

        Without ``as_of``, preserve the existing behavior and return edges
        regardless of their validity interval. When ``as_of`` is supplied,
        return edges whose stored validity interval includes that instant,
        using start-inclusive/end-exclusive boundaries. Missing boundaries
        permit candidate matching but do not prove indefinite validity.
        """
        self._validate_entity_type(entity_type)
        self._validate_uuid(user_id, "user_id")
        self._validate_uuid(entity_id, "entity_id")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100.")
        if as_of is not None:
            self._validate_as_of(as_of)

        await self._validate_endpoint(
            session,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        statement = select(KnowledgeRelationship).where(
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
        if as_of is not None:
            statement = statement.where(
                or_(
                    KnowledgeRelationship.valid_from.is_(None),
                    KnowledgeRelationship.valid_from <= as_of,
                ),
                or_(
                    KnowledgeRelationship.valid_until.is_(None),
                    KnowledgeRelationship.valid_until > as_of,
                ),
            )

        result = await session.scalars(
            statement.order_by(
                KnowledgeRelationship.created_at.desc(),
                KnowledgeRelationship.id,
            ).limit(limit)
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
            raise ValueError("One or more source chunks do not belong to the user.")

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
        persisted_by_chunk = {source.chunk_id: source for source in persisted_result.all()}
        # If the database did not return every requested row, fail loudly
        # rather than silently returning incomplete provenance.
        if set(persisted_by_chunk) != set(unique_chunk_ids):
            raise RuntimeError(
                "Relationship provenance insert completed without all rows persisted."
            )
        return [persisted_by_chunk[chunk_id] for chunk_id in unique_chunk_ids]

    @staticmethod
    def _validate_as_of(as_of: datetime) -> None:
        """Reject ambiguous timestamps for historical instant comparisons."""
        if not isinstance(as_of, datetime):
            raise ValueError("as_of must be a datetime.")
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware.")

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

    @staticmethod
    def _validate_validity_interval(
        valid_from: datetime | None,
        valid_until: datetime | None,
    ) -> None:
        """Validate an optional relationship validity interval."""

        for field_name, value in (
            ("valid_from", valid_from),
            ("valid_until", valid_until),
        ):
            if value is None:
                continue

            if not isinstance(value, datetime):
                raise ValueError(f"{field_name} must be a datetime or None.")

            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{field_name} must be timezone-aware.")

        if valid_from is not None and valid_until is not None and valid_until <= valid_from:
            raise ValueError("valid_until must be later than valid_from.")
