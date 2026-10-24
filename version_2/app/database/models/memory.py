from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.models.base_model import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.document import Document
    from app.database.models.document_chunk import DocumentChunk
    from app.database.models.user import User


class Memory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Persisted personal memory owned by a single user."""

    __tablename__ = "memories"

    __table_args__ = (
        CheckConstraint(
            "memory_type IN ('fact', 'preference', 'goal', 'constraint')",
            name="ck_memories_memory_type",
        ),
        CheckConstraint(
            "status IN ('active', 'superseded', 'expired')",
            name="ck_memories_status",
        ),
        CheckConstraint(
            "confidence IS NULL OR "
            "(confidence >= 0.0 AND confidence <= 1.0)",
            name="ck_memories_confidence_range",
        ),
        CheckConstraint(
            "valid_until IS NULL OR "
            "valid_from IS NULL OR "
            "valid_until > valid_from",
            name="ck_memories_validity_range",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    memory_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    normalized_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default="active",
        index=True,
    )

    confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    valid_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    valid_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("memories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    user: Mapped[User] = relationship(
        "User",
        back_populates="memories",
    )

    supersedes: Mapped[Memory | None] = relationship(
        "Memory",
        remote_side="Memory.id",
        foreign_keys=[supersedes_id],
    )

    sources: Mapped[list[MemorySource]] = relationship(
        "MemorySource",
        back_populates="memory",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class MemorySource(UUIDPrimaryKeyMixin, Base):
    """Provenance record linking a memory to its origin or evidence."""

    __tablename__ = "memory_sources"

    memory_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source_kind: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    source_reference: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    evidence_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    memory: Mapped[Memory] = relationship(
        "Memory",
        back_populates="sources",
    )

    document: Mapped[Document | None] = relationship(
        "Document",
    )

    chunk: Mapped[DocumentChunk | None] = relationship(
        "DocumentChunk",
    )