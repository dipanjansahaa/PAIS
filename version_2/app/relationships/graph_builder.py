"""Construct graph edges from explicit, user-owned domain associations.

This first graph-construction pass deliberately uses only persisted foreign-key
relationships. It does not infer links from similar names, free text, or LLM
output; those require a separate entity-linking policy and evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.commitment import Commitment, CommitmentSource
from app.database.models.decision import Decision, DecisionSource
from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.memory import Memory, MemorySource
from app.database.models.person import Person
from app.database.models.project import Project
from app.database.models.task import Task, TaskSource
from app.relationships.entity_linker import EntityLinkingService
from app.relationships.service import RelationshipService


@dataclass(frozen=True, slots=True)
class GraphConstructionResult:
    """Counts of explicit edges and evidence links processed by the pass."""

    relationships_processed: int = 0
    provenance_links_processed: int = 0
    person_links_matched: int = 0
    person_links_ambiguous: int = 0
    person_links_unmatched: int = 0


@dataclass(frozen=True, slots=True)
class _Edge:
    source_type: str
    source_id: UUID
    relationship_type: str
    target_type: str
    target_id: UUID
    chunk_ids: tuple[UUID, ...]


class KnowledgeGraphConstructionService:
    """Create idempotent graph edges from explicit PAIS domain associations.

    The service is additive: it creates missing edges and attaches available
    source chunks, but does not delete edges if an underlying association is
    later removed. Reconciliation requires tracking which edges were generated
    by this service versus manually created, which the current schema does not
    yet represent. The caller owns the transaction; this service never commits.
    """

    def __init__(
        self,
        *,
        relationship_service: RelationshipService | None = None,
        entity_linking_service: EntityLinkingService | None = None,
    ) -> None:
        self.relationship_service = relationship_service or RelationshipService()
        self.entity_linking_service = entity_linking_service or EntityLinkingService()

    async def construct_for_user(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
    ) -> GraphConstructionResult:
        """Create graph edges supported by explicit associations for one user."""
        projects = list(
            (await session.scalars(select(Project).where(Project.user_id == user_id))).all()
        )
        documents = list(
            (await session.scalars(select(Document).where(Document.user_id == user_id))).all()
        )
        tasks = list((await session.scalars(select(Task).where(Task.user_id == user_id))).all())
        commitments = list(
            (await session.scalars(select(Commitment).where(Commitment.user_id == user_id))).all()
        )
        decisions = list(
            (await session.scalars(select(Decision).where(Decision.user_id == user_id))).all()
        )
        memories = list(
            (await session.scalars(select(Memory).where(Memory.user_id == user_id))).all()
        )
        people = list(
            (await session.scalars(select(Person).where(Person.user_id == user_id))).all()
        )

        project_ids = {project.id for project in projects}
        commitment_ids = {commitment.id for commitment in commitments}
        memory_ids = {memory.id for memory in memories}

        document_chunk_rows = (
            await session.execute(
                select(DocumentChunk.document_id, DocumentChunk.id)
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(Document.user_id == user_id)
            )
        ).all()
        document_sources = _group_pairs(document_chunk_rows)

        task_source_rows = list(
            (
                await session.scalars(
                    select(TaskSource)
                    .join(Task, Task.id == TaskSource.task_id)
                    .where(Task.user_id == user_id)
                )
            ).all()
        )
        commitment_source_rows = list(
            (
                await session.scalars(
                    select(CommitmentSource)
                    .join(Commitment, Commitment.id == CommitmentSource.commitment_id)
                    .where(Commitment.user_id == user_id)
                )
            ).all()
        )
        decision_source_rows = list(
            (
                await session.scalars(
                    select(DecisionSource)
                    .join(Decision, Decision.id == DecisionSource.decision_id)
                    .where(Decision.user_id == user_id)
                )
            ).all()
        )
        memory_source_rows = list(
            (
                await session.scalars(
                    select(MemorySource)
                    .join(Memory, Memory.id == MemorySource.memory_id)
                    .where(Memory.user_id == user_id)
                )
            ).all()
        )

        task_sources = _group_sources(task_source_rows, "task_id")
        commitment_sources = _group_sources(commitment_source_rows, "commitment_id")
        decision_sources = _group_sources(decision_source_rows, "decision_id")
        memory_sources = _group_sources(memory_source_rows, "memory_id")

        edges: list[_Edge] = []
        person_links_matched = 0
        person_links_ambiguous = 0
        person_links_unmatched = 0

        for document in documents:
            if document.project_id in project_ids:
                edges.append(
                    _Edge(
                        "document",
                        document.id,
                        "belongs_to",
                        "project",
                        document.project_id,
                        tuple(document_sources.get(document.id, ())),
                    )
                )

        for task in tasks:
            owner_link = self.entity_linking_service.resolve_person_reference(
                task.owner, people=people
            )
            if task.owner and owner_link.status == "matched":
                edges.append(
                    _Edge(
                        "task",
                        task.id,
                        "assigned_to",
                        "person",
                        owner_link.person_id,
                        tuple(task_sources.get(task.id, ())),
                    )
                )
                person_links_matched += 1
            elif task.owner and owner_link.status == "ambiguous":
                person_links_ambiguous += 1
            elif task.owner:
                person_links_unmatched += 1

            if task.project_id in project_ids:
                edges.append(
                    _Edge(
                        "task",
                        task.id,
                        "belongs_to",
                        "project",
                        task.project_id,
                        tuple(task_sources.get(task.id, ())),
                    )
                )
            if task.commitment_id in commitment_ids:
                evidence = _ordered_unique(
                    [
                        *commitment_sources.get(task.commitment_id, ()),
                        *task_sources.get(task.id, ()),
                    ]
                )
                # The commitment is the obligation; the task is the action that
                # fulfills it. This direction follows the relationship vocabulary.
                edges.append(
                    _Edge(
                        "commitment",
                        task.commitment_id,
                        "fulfills",
                        "task",
                        task.id,
                        tuple(evidence),
                    )
                )

        for commitment in commitments:
            owner_link = self.entity_linking_service.resolve_person_reference(
                commitment.owner, people=people
            )
            if commitment.owner and owner_link.status == "matched":
                edges.append(
                    _Edge(
                        "commitment",
                        commitment.id,
                        "assigned_to",
                        "person",
                        owner_link.person_id,
                        tuple(commitment_sources.get(commitment.id, ())),
                    )
                )
                person_links_matched += 1
            elif commitment.owner and owner_link.status == "ambiguous":
                person_links_ambiguous += 1
            elif commitment.owner:
                person_links_unmatched += 1

            if commitment.project_id in project_ids:
                edges.append(
                    _Edge(
                        "commitment",
                        commitment.id,
                        "belongs_to",
                        "project",
                        commitment.project_id,
                        tuple(commitment_sources.get(commitment.id, ())),
                    )
                )

        for decision in decisions:
            if decision.project_id in project_ids:
                edges.append(
                    _Edge(
                        "decision",
                        decision.id,
                        "belongs_to",
                        "project",
                        decision.project_id,
                        tuple(decision_sources.get(decision.id, ())),
                    )
                )

        for memory in memories:
            if (
                memory.supersedes_id is not None
                and memory.supersedes_id in memory_ids
                and memory.supersedes_id != memory.id
            ):
                edges.append(
                    _Edge(
                        "memory",
                        memory.id,
                        "supersedes",
                        "memory",
                        memory.supersedes_id,
                        tuple(memory_sources.get(memory.id, ())),
                    )
                )

        provenance_count = 0
        for edge in edges:
            relationship = await self.relationship_service.create_relationship(
                session,
                user_id=user_id,
                source_type=edge.source_type,
                source_id=edge.source_id,
                relationship_type=edge.relationship_type,
                target_type=edge.target_type,
                target_id=edge.target_id,
            )
            if edge.chunk_ids:
                await self.relationship_service.add_sources(
                    session,
                    user_id=user_id,
                    relationship_id=relationship.id,
                    chunk_ids=list(edge.chunk_ids),
                )
                provenance_count += len(edge.chunk_ids)

        await session.flush()
        return GraphConstructionResult(
            relationships_processed=len(edges),
            provenance_links_processed=provenance_count,
            person_links_matched=person_links_matched,
            person_links_ambiguous=person_links_ambiguous,
            person_links_unmatched=person_links_unmatched,
        )


def _group_pairs(rows) -> dict[UUID, list[UUID]]:
    grouped: dict[UUID, list[UUID]] = {}
    for owner_id, chunk_id in rows:
        grouped.setdefault(owner_id, []).append(chunk_id)
    return {key: _ordered_unique(value) for key, value in grouped.items()}


def _group_sources(rows, owner_field: str) -> dict[UUID, list[UUID]]:
    grouped: dict[UUID, list[UUID]] = {}
    for row in rows:
        grouped.setdefault(getattr(row, owner_field), []).append(row.chunk_id)
    return {key: _ordered_unique(value) for key, value in grouped.items()}


def _ordered_unique(values: list[UUID]) -> list[UUID]:
    return list(dict.fromkeys(values))
