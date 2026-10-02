"""Observable wrapper around the provider-independent LLM interface."""

from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from uuid import UUID

import logging
logger = logging.getLogger(__name__)

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import AsyncSessionFactory
from app.llm.base import LLMProvider
from app.llm.models import LLMResponse, Message
from app.observability.models import ModelRunOperation
from app.observability.service import ModelRunRecorder


class TrackedLLMProvider(LLMProvider):
    """Wrap an LLM provider and record every invocation."""

    def __init__(
        self,
        *,
        provider: LLMProvider,
        user_id: UUID,
        operation: ModelRunOperation,
        provider_name: str,
        session: AsyncSession | None = None,
        recorder: ModelRunRecorder | None = None,
    ) -> None:
        self.provider = provider
        self.user_id = user_id
        self.operation = operation
        self.provider_name = provider_name

        if recorder is not None:
            self.recorder = recorder
        else:
            if session is None:
                raise ValueError(
                    "session is required when recorder is not provided."
                )

            self.recorder = ModelRunRecorder(
                session=session,
            )

    async def generate(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        response_schema: type | None = None,
    ) -> LLMResponse:
        """Generate a response and record its execution metadata."""

        started_at = datetime.now(timezone.utc)
        started_perf = perf_counter()

        try:
            response = await self.provider.generate(
                messages,
                temperature=temperature,
                response_schema=response_schema,
            )
        except Exception as exc:
            latency_ms = (
                perf_counter() - started_perf
            ) * 1000

            try:
                await self.recorder.record_failed(
                    user_id=self.user_id,
                    operation=self.operation,
                    provider=self.provider_name,
                    temperature=temperature,
                    started_at=started_at,
                    latency_ms=latency_ms,
                    error=exc,
                )
            except Exception:
                logger.exception(
                    "Failed to record LLM model-run failure telemetry."
                )

            raise

        latency_ms = (
            perf_counter() - started_perf
        ) * 1000

        try:
            await self.recorder.record_completed(
                user_id=self.user_id,
                operation=self.operation,
                provider=self.provider_name,
                temperature=temperature,
                started_at=started_at,
                response=response,
                latency_ms=latency_ms,
            )
        except Exception:
            logger.exception(
                "Failed to record LLM model-run success telemetry."
            )

        return response