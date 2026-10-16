from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.models.base_model import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.document_chunk import DocumentChunk
    from app.database.models.project import Project
    from app.database.models.user import User


class Decision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Persisted user decision."""

    __tablename__ = "decisions"

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

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    decision_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
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
        back_populates="decisions",
    )

    project: Mapped[Project | None] = relationship(
        "Project",
        back_populates="decisions",
    )

    sources: Mapped[list[DecisionSource]] = relationship(
        "DecisionSource",
        back_populates="decision",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class DecisionSource(Base):
    """Provenance linking a decision to source chunks."""

    __tablename__ = "decision_sources"

    decision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decisions.id", ondelete="CASCADE"),
        primary_key=True,
    )

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )

    decision: Mapped[Decision] = relationship(
        "Decision",
        back_populates="sources",
    )

    chunk: Mapped[DocumentChunk] = relationship(
        "DocumentChunk",
    )