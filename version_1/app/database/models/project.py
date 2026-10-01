from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.models.base_model import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.commitment import Commitment
    from app.database.models.decision import Decision
    from app.database.models.document import Document
    from app.database.models.document_chunk import DocumentChunk
    from app.database.models.task import Task
    from app.database.models.user import User


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user-owned project used to organize PAIS knowledge and actions."""

    __tablename__ = "projects"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default="active",
    )

    user: Mapped[User] = relationship(
        "User",
        back_populates="projects",
    )

    documents: Mapped[list[Document]] = relationship(
        "Document",
        back_populates="project",
        passive_deletes=True,
    )

    tasks: Mapped[list[Task]] = relationship(
        "Task",
        back_populates="project",
        passive_deletes=True,
    )

    decisions: Mapped[list[Decision]] = relationship(
        "Decision",
        back_populates="project",
        passive_deletes=True,
    )

    commitments: Mapped[list[Commitment]] = relationship(
        "Commitment",
        back_populates="project",
        passive_deletes=True,
    )

    sources: Mapped[list[ProjectSource]] = relationship(
        "ProjectSource",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ProjectSource(Base):
    """Provenance linking a project to its source document chunks."""

    __tablename__ = "project_sources"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "projects.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "document_chunks.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
        index=True,
    )

    project: Mapped[Project] = relationship(
        "Project",
        back_populates="sources",
    )

    chunk: Mapped[DocumentChunk] = relationship(
        "DocumentChunk",
    )