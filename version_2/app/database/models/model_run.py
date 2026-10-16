"""SQLAlchemy model for persisted LLM model runs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.models.base_model import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.user import User


class ModelRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Persisted observability record for one LLM invocation."""

    __tablename__ = "model_runs"

    # Intentionally not a foreign key.
    #
    # Model runs are telemetry and are persisted independently from the
    # request/business transaction. This allows failed LLM calls and
    # first-request user bootstrap to be recorded without coupling
    # observability persistence to the application transaction.
    user_id: Mapped[uuid.UUID] = mapped_column(
        nullable=False,
        index=True,
    )

    operation: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )

    provider: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    model: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    temperature: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    prompt_tokens: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    completion_tokens: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    total_tokens: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    latency_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    finish_reason: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    error_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    user: Mapped[User | None] = relationship(
        "User",
        primaryjoin="foreign(ModelRun.user_id) == User.id",
        viewonly=True,
    )