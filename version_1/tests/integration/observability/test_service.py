"""Integration tests for model-run observability persistence."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.database.models.model_run import ModelRun
from app.llm.models import LLMResponse, TokenUsage
from app.observability.models import (
    ModelRunOperation,
)
from app.observability.service import ModelRunRecorder


@pytest.mark.asyncio
async def test_record_completed_persists_model_run(db_session) -> None:
    """A completed model run should be persisted to the database."""

    user_id = uuid4()

    recorder = ModelRunRecorder(
        session=db_session,
    )

    started_at = datetime.now(timezone.utc)

    response = LLMResponse(
        content="integration response",
        model="llama3.2:3b",
        usage=TokenUsage(
            prompt_tokens=12,
            completion_tokens=24,
            total_tokens=36,
        ),
        latency_ms=100.0,
        finish_reason="stop",
    )

    await recorder.record_completed(
        user_id=user_id,
        operation=ModelRunOperation.QUERY,
        provider="ollama",
        temperature=0.0,
        started_at=started_at,
        response=response,
        latency_ms=125.5,
    )

    await db_session.commit()

    result = await db_session.execute(
        select(ModelRun).where(
            ModelRun.user_id == user_id,
        )
    )

    stored = result.scalar_one()

    assert stored.user_id == user_id
    assert stored.operation == "query"
    assert stored.status == "completed"
    assert stored.provider == "ollama"
    assert stored.model == "llama3.2:3b"
    assert stored.temperature == 0.0
    assert stored.prompt_tokens == 12
    assert stored.completion_tokens == 24
    assert stored.total_tokens == 36
    assert stored.latency_ms == 125.5
    assert stored.finish_reason == "stop"
    assert stored.error_type is None
    assert stored.started_at == started_at


@pytest.mark.asyncio
async def test_record_failed_persists_model_run(db_session) -> None:
    """A failed model run should be persisted with its error type."""

    user_id = uuid4()

    recorder = ModelRunRecorder(
        session=db_session,
    )

    started_at = datetime.now(timezone.utc)
    error = TimeoutError("LLM request timed out")

    await recorder.record_failed(
        user_id=user_id,
        operation=ModelRunOperation.DAILY_GENERATION,
        provider="ollama",
        temperature=0.0,
        started_at=started_at,
        latency_ms=2500.0,
        error=error,
    )

    await db_session.commit()

    result = await db_session.execute(
        select(ModelRun).where(
            ModelRun.user_id == user_id,
        )
    )

    stored = result.scalar_one()

    assert stored.user_id == user_id
    assert stored.operation == "daily_generation"
    assert stored.status == "failed"
    assert stored.provider == "ollama"
    assert stored.model is None
    assert stored.temperature == 0.0
    assert stored.prompt_tokens is None
    assert stored.completion_tokens is None
    assert stored.total_tokens is None
    assert stored.latency_ms == 2500.0
    assert stored.finish_reason is None
    assert stored.error_type == "TimeoutError"
    assert stored.started_at == started_at


@pytest.mark.asyncio
async def test_record_completed_preserves_token_usage(
    db_session,
) -> None:
    """Token usage should be persisted without modification."""

    user_id = uuid4()

    recorder = ModelRunRecorder(
        session=db_session,
    )

    response = LLMResponse(
        content="token test",
        model="llama3.2:3b",
        usage=TokenUsage(
            prompt_tokens=101,
            completion_tokens=202,
            total_tokens=303,
        ),
        latency_ms=200.0,
        finish_reason="stop",
    )

    await recorder.record_completed(
        user_id=user_id,
        operation=ModelRunOperation.QUERY,
        provider="ollama",
        temperature=0.1,
        started_at=datetime.now(timezone.utc),
        response=response,
        latency_ms=200.0,
    )

    await db_session.commit()

    result = await db_session.execute(
        select(ModelRun).where(
            ModelRun.user_id == user_id,
        )
    )

    stored = result.scalar_one()

    assert stored.prompt_tokens == 101
    assert stored.completion_tokens == 202
    assert stored.total_tokens == 303


@pytest.mark.asyncio
async def test_model_run_preserves_user_and_operation(
    db_session,
) -> None:
    """User identity and operation type should be persisted correctly."""

    user_id = uuid4()

    recorder = ModelRunRecorder(
        session=db_session,
    )

    response = LLMResponse(
        content="operation test",
        model="llama3.2:3b",
        usage=None,
        latency_ms=75.0,
        finish_reason="stop",
    )

    await recorder.record_completed(
        user_id=user_id,
        operation=ModelRunOperation.STRUCTURED_INTELLIGENCE,
        provider="ollama",
        temperature=0.0,
        started_at=datetime.now(timezone.utc),
        response=response,
        latency_ms=75.0,
    )

    await db_session.commit()

    result = await db_session.execute(
        select(ModelRun).where(
            ModelRun.user_id == user_id,
        )
    )

    stored = result.scalar_one()

    assert stored.user_id == user_id
    assert stored.operation == "structured_intelligence"