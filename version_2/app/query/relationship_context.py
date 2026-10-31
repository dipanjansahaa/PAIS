"""Build provenance-aware context from a user's stored knowledge relationships."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.commitment import Commitment
from app.database.models.decision import Decision
from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.knowledge_relationship import (
    KnowledgeRelationship,
    KnowledgeRelationshipSource,
)
from app.database.models.memory import Memory
from app.database.models.person import Person
from app.database.models.project import Project
from app.database.models.risk import Risk
from app.database.models.task import Task
from app.relationships.service import RelationshipService

_ENTITY_LABELS = {
    "project": (Project, "name"),
    "person": (Person, "name"),
    "task": (Task, "description"),
    "commitment": (Commitment, "description"),
    "decision": (Decision, "title"),
    "risk": (Risk, "title"),
    "document": (Document, "title"),
    "memory": (Memory, "content"),
}


@dataclass(frozen=True, slots=True)
class QueryRelationshipSource:
    """A source chunk supporting a stored relationship."""

    citation_id: str
    chunk_id: str
    document_id: str
    document_title: str
    content: str


@dataclass(frozen=True, slots=True)
class QueryRelationship:
    """A relationship and its user-owned endpoint labels and provenance."""

    citation_id: str
    relationship_id: str
    source_type: str
    source_id: str
    source_label: str
    relationship_type: str
    target_type: str
    target_id: str
    target_label: str
    valid_from: datetime | None
    valid_until: datetime | None
    sources: tuple[QueryRelationshipSource, ...]


@dataclass(frozen=True, slots=True)
class RelationshipContext:
    """Relationship records and the deterministic text sent to the LLM."""

    text: str
    relationships: tuple[QueryRelationship, ...]


class RelationshipContextBuilder:
    """Load graph context for one explicit, user-owned seed entity.

    The builder does not infer an entity from query text. Callers must provide
    a concrete entity type and UUID, avoiding accidental graph traversal from
    ambiguous names. The caller owns the database transaction.
    """

    def __init__(
        self,
        *,
        relationship_service: RelationshipService | None = None,
        max_label_chars: int = 400,
        max_source_chars: int = 1200,
        max_sources_per_relationship: int = 3,
    ) -> None:
        if max_label_chars <= 0 or max_source_chars <= 0 or max_sources_per_relationship <= 0:
            raise ValueError("Text limits must be greater than zero.")
        self.relationship_service = relationship_service or RelationshipService()
        self.max_label_chars = max_label_chars
        self.max_source_chars = max_source_chars
        self.max_sources_per_relationship = max_sources_per_relationship

    async def build(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        entity_type: str,
        entity_id: UUID,
        limit: int = 20,
        as_of: datetime | None = None,
    ) -> RelationshipContext:
        """Build relationship context while preserving user isolation."""
        # Query context represents the graph at the current instant unless a
        # caller explicitly requests a historical valid-time snapshot.
        effective_as_of = as_of if as_of is not None else datetime.now(UTC)
        relationships = await self.relationship_service.list_for_entity(
            session,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            limit=limit,
            as_of=effective_as_of,
        )
        if not relationships:
            return RelationshipContext(text="", relationships=())

        labels = await self._load_endpoint_labels(
            session,
            user_id=user_id,
            relationships=relationships,
        )
        sources = await self._load_sources(
            session,
            user_id=user_id,
            relationships=relationships,
        )

        result: list[QueryRelationship] = []
        for relationship in relationships:
            source_label = labels.get((relationship.source_type, relationship.source_id))
            target_label = labels.get((relationship.target_type, relationship.target_id))
            # Polymorphic endpoints have no database foreign key. Skip stale
            # edges rather than presenting a relationship with an unresolved
            # or potentially cross-user endpoint.
            if source_label is None or target_label is None:
                continue

            citation_id = f"R{len(result) + 1}"
            relationship_sources = tuple(
                QueryRelationshipSource(
                    citation_id=f"{citation_id}-C{index}",
                    chunk_id=str(chunk_id),
                    document_id=str(document_id),
                    document_title=document_title,
                    content=content[: self.max_source_chars],
                )
                for index, (chunk_id, document_id, document_title, content) in enumerate(
                    sources.get(relationship.id, ())[: self.max_sources_per_relationship],
                    start=1,
                )
            )
            result.append(
                QueryRelationship(
                    citation_id=citation_id,
                    relationship_id=str(relationship.id),
                    source_type=relationship.source_type,
                    source_id=str(relationship.source_id),
                    source_label=source_label,
                    relationship_type=relationship.relationship_type,
                    target_type=relationship.target_type,
                    target_id=str(relationship.target_id),
                    target_label=target_label,
                    valid_from=relationship.valid_from,
                    valid_until=relationship.valid_until,
                    sources=relationship_sources,
                )
            )

        lines: list[str] = []
        for relationship in result:
            line = (
                f"[{relationship.citation_id}] "
                f'{relationship.source_type} "{relationship.source_label}" '
                f"--{relationship.relationship_type}--> "
                f'{relationship.target_type} "{relationship.target_label}"'
            )
            line += (
                f" (valid_from={relationship.valid_from!s}; "
                f"valid_until={relationship.valid_until!s})"
            )
            if relationship.valid_from is None or relationship.valid_until is None:
                line += (
                    " [validity boundaries incomplete: null means unknown, "
                    "not proof of indefinite validity]"
                )
            lines.append(line)
            for source in relationship.sources:
                lines.append(
                    f"[{source.citation_id}] Relationship evidence from "
                    f"{source.document_title!r}: {source.content}"
                )

        return RelationshipContext(text="\n".join(lines), relationships=tuple(result))

    async def _load_endpoint_labels(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        relationships: list[KnowledgeRelationship],
    ) -> dict[tuple[str, UUID], str]:
        endpoint_ids: dict[str, set[UUID]] = {}
        for relationship in relationships:
            endpoint_ids.setdefault(relationship.source_type, set()).add(relationship.source_id)
            endpoint_ids.setdefault(relationship.target_type, set()).add(relationship.target_id)

        labels: dict[tuple[str, UUID], str] = {}
        for entity_type, ids in endpoint_ids.items():
            model, label_field = _ENTITY_LABELS[entity_type]
            label_column = getattr(model, label_field)
            rows = await session.execute(
                select(model.id, label_column).where(
                    model.user_id == user_id,
                    model.id.in_(ids),
                )
            )
            for entity_id, raw_label in rows.all():
                label = " ".join(str(raw_label or "").split())
                if label:
                    labels[(entity_type, entity_id)] = label[: self.max_label_chars]
        return labels

    async def _load_sources(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        relationships: list[KnowledgeRelationship],
    ) -> dict[UUID, list[tuple[UUID, UUID, str, str]]]:
        relationship_ids = [relationship.id for relationship in relationships]
        rows = await session.execute(
            select(
                KnowledgeRelationshipSource.relationship_id,
                DocumentChunk.id,
                Document.id,
                Document.title,
                DocumentChunk.content,
            )
            .join(
                KnowledgeRelationship,
                KnowledgeRelationship.id == KnowledgeRelationshipSource.relationship_id,
            )
            .join(
                DocumentChunk,
                DocumentChunk.id == KnowledgeRelationshipSource.chunk_id,
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                KnowledgeRelationship.user_id == user_id,
                Document.user_id == user_id,
                KnowledgeRelationship.id.in_(relationship_ids),
            )
            .order_by(
                KnowledgeRelationshipSource.relationship_id,
                DocumentChunk.chunk_index,
                DocumentChunk.id,
            )
        )
        grouped: dict[UUID, list[tuple[UUID, UUID, str, str]]] = {}
        for relationship_id, chunk_id, document_id, document_title, content in rows.all():
            grouped.setdefault(relationship_id, []).append(
                (chunk_id, document_id, document_title, content)
            )
        return grouped
