from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.models.base_model import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.document import Document
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