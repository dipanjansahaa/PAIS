from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.models.base_model import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.document_chunk import DocumentChunk
    from app.database.models.user import User


class Risk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "risks"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    severity: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    user: Mapped[User] = relationship(
        "User",
        back_populates="risks",
    )

    sources: Mapped[list[RiskSource]] = relationship(
        "RiskSource",
        back_populates="risk",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class RiskSource(Base):
    __tablename__ = "risk_sources"

    risk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("risks.id", ondelete="CASCADE"),
        primary_key=True,
    )

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )

    risk: Mapped[Risk] = relationship(
        "Risk",
        back_populates="sources",
    )

    chunk: Mapped[DocumentChunk] = relationship(
        "DocumentChunk",
    )