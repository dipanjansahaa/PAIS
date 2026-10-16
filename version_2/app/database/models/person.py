from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.models.base_model import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.document_chunk import DocumentChunk
    from app.database.models.user import User


class Person(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user-owned person extracted from PAIS source material."""

    __tablename__ = "people"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    email: Mapped[str | None] = mapped_column(
        String(320),
        nullable=True,
    )

    user: Mapped[User] = relationship(
        "User",
        back_populates="people",
    )

    sources: Mapped[list[PersonSource]] = relationship(
        "PersonSource",
        back_populates="person",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class PersonSource(Base):
    """Provenance linking a person to source document chunks."""

    __tablename__ = "person_sources"

    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "people.id",
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

    person: Mapped[Person] = relationship(
        "Person",
        back_populates="sources",
    )

    chunk: Mapped[DocumentChunk] = relationship(
        "DocumentChunk",
    )