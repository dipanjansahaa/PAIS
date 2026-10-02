"""Persistence services for LLM model-run observability."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models.model_run import ModelRun
from app.llm.models import LLMResponse
from app.observability.models import (
    ModelRunOperation,
    ModelRunStatus,
)


logger = logging.getLogger(__name__)


class ModelRunRecorder:
    """Persist LLM execution metadata using the caller-owned database session."""

    def __init__(
        self,
        *,
        session: AsyncSession,
    ) -> None:
        self.session = session

    async def record_completed(
        self,
        *,
        user_id: UUID,
        operation: ModelRunOperation,
        provider: str,
        temperature: float,
        started_at: datetime,
        response: LLMResponse,
        latency_ms: float,
    ) -> None:
        """Persist a successful model run."""

        usage = response.usage

        await self._persist(
            user_id=user_id,
            operation=operation,
            status=ModelRunStatus.COMPLETED,
            provider=provider,
            model=response.model,
            temperature=temperature,
            prompt_tokens=(
                usage.prompt_tokens
                if usage is not None
                else None
            ),
            completion_tokens=(
                usage.completion_tokens
                if usage is not None
                else None
            ),
            total_tokens=(
                usage.total_tokens
                if usage is not None
                else None
            ),
            latency_ms=latency_ms,
            finish_reason=response.finish_reason,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            error_type=None,
        )

    async def record_failed(
        self,
        *,
        user_id: UUID,
        operation: ModelRunOperation,
        provider: str,
        temperature: float,
        started_at: datetime,
        latency_ms: float,
        error: Exception,
    ) -> None:
        """Persist a failed model run."""

        await self._persist(
            user_id=user_id,
            operation=operation,
            status=ModelRunStatus.FAILED,
            provider=provider,
            model=None,
            temperature=temperature,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            latency_ms=latency_ms,
            finish_reason=None,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            error_type=type(error).__name__,
        )

    async def _persist(
        self,
        *,
        user_id: UUID,
        operation: ModelRunOperation,
        status: ModelRunStatus,
        provider: str,
        model: str | None,
        temperature: float,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        total_tokens: int | None,
        latency_ms: float,
        finish_reason: str | None,
        started_at: datetime,
        completed_at: datetime,
        error_type: str | None,
    ) -> None:
        """Persist one model-run record."""

        model_run = ModelRun(
            user_id=user_id,
            operation=operation.value,
            status=status.value,
            provider=provider,
            model=model,
            temperature=temperature,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            finish_reason=finish_reason,
            started_at=started_at,
            completed_at=completed_at,
            error_type=error_type,
        )

        try:
            async with self.session.begin_nested():
                self.session.add(model_run)
                await self.session.flush()
        except Exception:
            # Observability must never break the actual LLM request.
            logger.exception(
                "Failed to persist LLM model-run telemetry."
            )