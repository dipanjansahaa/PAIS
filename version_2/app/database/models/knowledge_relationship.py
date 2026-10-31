from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.models.base_model import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.document_chunk import DocumentChunk
    from app.database.models.user import User


KNOWLEDGE_ENTITY_TYPES = (
    "project",
    "person",
    "task",
    "commitment",
    "decision",
    "risk",
    "document",
    "memory",
)

KNOWLEDGE_RELATIONSHIP_TYPES = (
    "related_to",
    "depends_on",
    "blocks",
    "assigned_to",
    "affects",
    "supports",
    "contradicts",
    "caused_by",
    "supersedes",
    "belongs_to",
    "references",
    "mitigates",
    "threatens",
    "fulfills",
    "derived_from",
)

_ENTITY_TYPE_SQL = ", ".join(f"'{value}'" for value in KNOWLEDGE_ENTITY_TYPES)
_RELATIONSHIP_TYPE_SQL = ", ".join(
    f"'{value}'" for value in KNOWLEDGE_RELATIONSHIP_TYPES
)


class KnowledgeRelationship(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A directed, user-owned relationship between two PAIS domain entities.

    The endpoint IDs are polymorphic UUIDs, so their target tables cannot be
    enforced with ordinary foreign keys. The relationship service must validate
    endpoint existence and ownership before inserting records.
    """

    __tablename__ = "knowledge_relationships"

    __table_args__ = (
        CheckConstraint(
            f"source_type IN ({_ENTITY_TYPE_SQL})",
            name="ck_knowledge_relationships_source_type",
        ),
        CheckConstraint(
            f"target_type IN ({_ENTITY_TYPE_SQL})",
            name="ck_knowledge_relationships_target_type",
        ),
        CheckConstraint(
            f"relationship_type IN ({_RELATIONSHIP_TYPE_SQL})",
            name="ck_knowledge_relationships_relationship_type",
        ),
        CheckConstraint(
            "source_type != target_type OR source_id != target_id",
            name="ck_knowledge_relationships_no_self_reference",
        ),
        UniqueConstraint(
            "user_id",
            "source_type",
            "source_id",
            "relationship_type",
            "target_type",
            "target_id",
            name="uq_knowledge_relationships_directed_edge",
        ),
        Index(
            "ix_knowledge_relationships_source",
            "user_id",
            "source_type",
            "source_id",
        ),
        Index(
            "ix_knowledge_relationships_target",
            "user_id",
            "target_type",
            "target_id",
        ),
        Index(
            "ix_knowledge_relationships_type",
            "user_id",
            "relationship_type",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        nullable=False,
    )

    relationship_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    target_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    target_id: Mapped[uuid.UUID] = mapped_column(
        nullable=False,
    )

    user: Mapped[User] = relationship(
        "User",
        back_populates="knowledge_relationships",
    )

    sources: Mapped[list[KnowledgeRelationshipSource]] = relationship(
        "KnowledgeRelationshipSource",
        back_populates="knowledge_relationship",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class KnowledgeRelationshipSource(Base):
    """Evidence provenance linking a relationship to a source document chunk."""

    __tablename__ = "knowledge_relationship_sources"

    relationship_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_relationships.id", ondelete="CASCADE"),
        primary_key=True,
    )

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )

    knowledge_relationship: Mapped[KnowledgeRelationship] = relationship(
        "KnowledgeRelationship",
        back_populates="sources",
    )

    chunk: Mapped[DocumentChunk] = relationship("DocumentChunk")