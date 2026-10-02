"""Unit tests for model-run observability persistence."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.llm.models import LLMResponse, TokenUsage
from app.observability.models import (
    ModelRunOperation,
    ModelRunStatus,
)
from app.observability.service import ModelRunRecorder


class FakeNestedTransaction:
    """Async context manager representing a nested transaction."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None


class FakeSession:
    """Minimal async session fake for recorder tests."""

    def __init__(self) -> None:
        self.added = []
        self.flush_called = False

    def add(self, value) -> None:
        self.added.append(value)

    def begin_nested(self) -> FakeNestedTransaction:
        return FakeNestedTransaction()

    async def flush(self) -> None:
        self.flush_called = True


class FailingSession:
    """Session fake that fails during persistence."""

    def add(self, value) -> None:
        raise RuntimeError("database unavailable")

    def begin_nested(self) -> FakeNestedTransaction:
        return FakeNestedTransaction()

    async def flush(self) -> None:
        raise AssertionError("flush should not be reached")


@pytest.mark.asyncio
async def test_record_completed_persists_model_run() -> None:
    """A successful LLM response should create completed telemetry."""

    session = FakeSession()
    recorder = ModelRunRecorder(session=session)

    user_id = uuid4()
    started_at = datetime.now(timezone.utc)

    response = LLMResponse(
        content="test response",
        model="llama3.2:3b",
        usage=TokenUsage(
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        ),
        latency_ms=123.4,
        finish_reason="stop",
    )

    await recorder.record_completed(
        user_id=user_id,
        operation=ModelRunOperation.QUERY,
        provider="ollama",
        temperature=0.0,
        started_at=started_at,
        response=response,
        latency_ms=150.5,
    )

    assert len(session.added) == 1
    assert session.flush_called is True

    model_run = session.added[0]

    assert model_run.user_id == user_id
    assert model_run.operation == "query"
    assert model_run.status == "completed"
    assert model_run.provider == "ollama"
    assert model_run.model == "llama3.2:3b"
    assert model_run.temperature == 0.0
    assert model_run.prompt_tokens == 10
    assert model_run.completion_tokens == 20
    assert model_run.total_tokens == 30
    assert model_run.latency_ms == 150.5
    assert model_run.finish_reason == "stop"
    assert model_run.error_type is None
    assert model_run.started_at == started_at
    assert model_run.completed_at >= started_at


@pytest.mark.asyncio
async def test_record_completed_handles_missing_usage() -> None:
    """A response without token usage should persist null token fields."""

    session = FakeSession()
    recorder = ModelRunRecorder(session=session)

    response = LLMResponse(
        content="test response",
        model="llama3.2:3b",
        usage=None,
        latency_ms=100.0,
        finish_reason=None,
    )

    await recorder.record_completed(
        user_id=uuid4(),
        operation=ModelRunOperation.QUERY,
        provider="ollama",
        temperature=0.2,
        started_at=datetime.now(timezone.utc),
        response=response,
        latency_ms=100.0,
    )

    model_run = session.added[0]

    assert model_run.prompt_tokens is None
    assert model_run.completion_tokens is None
    assert model_run.total_tokens is None
    assert model_run.finish_reason is None


@pytest.mark.asyncio
async def test_record_failed_persists_failed_model_run() -> None:
    """A failed LLM invocation should create failed telemetry."""

    session = FakeSession()
    recorder = ModelRunRecorder(session=session)

    user_id = uuid4()
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

    assert len(session.added) == 1
    assert session.flush_called is True

    model_run = session.added[0]

    assert model_run.user_id == user_id
    assert model_run.operation == "daily_generation"
    assert model_run.status == "failed"
    assert model_run.provider == "ollama"
    assert model_run.model is None
    assert model_run.temperature == 0.0
    assert model_run.prompt_tokens is None
    assert model_run.completion_tokens is None
    assert model_run.total_tokens is None
    assert model_run.latency_ms == 2500.0
    assert model_run.finish_reason is None
    assert model_run.error_type == "TimeoutError"
    assert model_run.started_at == started_at
    assert model_run.completed_at >= started_at


@pytest.mark.asyncio
async def test_recorder_failure_does_not_raise() -> None:
    """Telemetry persistence failure must never escape the recorder."""

    recorder = ModelRunRecorder(
        session=FailingSession(),
    )

    response = LLMResponse(
        content="test response",
        model="llama3.2:3b",
        usage=None,
        latency_ms=50.0,
        finish_reason="stop",
    )

    await recorder.record_completed(
        user_id=uuid4(),
        operation=ModelRunOperation.QUERY,
        provider="ollama",
        temperature=0.0,
        started_at=datetime.now(timezone.utc),
        response=response,
        latency_ms=50.0,
    )