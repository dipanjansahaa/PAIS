from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.models.base_model import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.commitment import Commitment
    from app.database.models.document_chunk import DocumentChunk
    from app.database.models.project import Project
    from app.database.models.user import User


class Task(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Persisted user task."""

    __tablename__ = "tasks"

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

    commitment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("commitments.id", ondelete="SET NULL"),
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

    due_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )

    priority: Mapped[str | None] = mapped_column(
        String(32),
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
        back_populates="tasks",
    )

    project: Mapped[Project | None] = relationship(
        "Project",
        back_populates="tasks",
    )

    commitment: Mapped[Commitment | None] = relationship(
        "Commitment",
        back_populates="tasks",
    )

    sources: Mapped[list[TaskSource]] = relationship(
        "TaskSource",
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class TaskSource(Base):
    """Provenance linking a task to source chunks."""

    __tablename__ = "task_sources"

    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        primary_key=True,
    )

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )

    task: Mapped[Task] = relationship(
        "Task",
        back_populates="sources",
    )

    chunk: Mapped[DocumentChunk] = relationship(
        "DocumentChunk",
    )