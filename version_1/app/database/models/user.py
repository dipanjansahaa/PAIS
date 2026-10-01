from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.models.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.database.models.decision import Decision

if TYPE_CHECKING:
    from app.database.models.commitment import Commitment
    from app.database.models.decision import Decision
    from app.database.models.document import Document
    from app.database.models.project import Project
    from app.database.models.task import Task
    from app.database.models.person import Person
    from app.database.models.risk import Risk


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Application user and owner of PAIS data."""

    __tablename__ = "users"

    email: Mapped[str | None] = mapped_column(
        String(320),
        nullable=True,
        unique=True,
        index=True,
    )

    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    projects: Mapped[list[Project]] = relationship(
        "Project",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    documents: Mapped[list[Document]] = relationship(
        "Document",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    tasks: Mapped[list[Task]] = relationship(
        "Task",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    decisions: Mapped[list[Decision]] = relationship(
        "Decision",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    commitments: Mapped[list[Commitment]] = relationship(
        "Commitment",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    people: Mapped[list[Person]] = relationship(
        "Person",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    risks: Mapped[list[Risk]] = relationship(
        "Risk",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )