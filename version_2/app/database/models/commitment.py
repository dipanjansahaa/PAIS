from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.models.base_model import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.document_chunk import DocumentChunk
    from app.database.models.project import Project
    from app.database.models.task import Task
    from app.database.models.user import User


class Commitment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Persisted user commitment."""

    __tablename__ = "commitments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    owner: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    deadline_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="open",
        server_default="open",
    )

    user: Mapped[User] = relationship(
        "User",
        back_populates="commitments",
    )

    project: Mapped[Project | None] = relationship(
        "Project",
        back_populates="commitments",
    )

    tasks: Mapped[list[Task]] = relationship(
        "Task",
        back_populates="commitment",
    )

    sources: Mapped[list[CommitmentSource]] = relationship(
        "CommitmentSource",
        back_populates="commitment",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class CommitmentSource(Base):
    """Provenance linking a commitment to source chunks."""

    __tablename__ = "commitment_sources"

    commitment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("commitments.id", ondelete="CASCADE"),
        primary_key=True,
    )

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )

    commitment: Mapped[Commitment] = relationship(
        "Commitment",
        back_populates="sources",
    )

    chunk: Mapped[DocumentChunk] = relationship(
        "DocumentChunk",
    )