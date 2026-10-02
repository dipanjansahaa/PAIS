"""Unit tests for the tracked LLM provider."""

from datetime import datetime
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest

from app.llm.models import LLMResponse, Message, TokenUsage
from app.llm.tracked import TrackedLLMProvider
from app.observability.models import (
    ModelRunOperation,
)


class FakeLLMProvider:
    """Fake LLM provider used by tracked-provider tests."""

    def __init__(
        self,
        *,
        response: LLMResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error

    async def generate(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        response_schema: type | None = None,
    ) -> LLMResponse:
        if self.error is not None:
            raise self.error

        assert self.response is not None
        return self.response


def build_response(
    *,
    usage: TokenUsage | None = None,
) -> LLMResponse:
    """Build a deterministic fake LLM response."""

    return LLMResponse(
        content="hello",
        model="llama3.2:3b",
        usage=usage,
        latency_ms=50.0,
        finish_reason="stop",
    )


def build_messages() -> list[Message]:
    """Build a minimal message list."""

    return [
        Message(
            role="user",
            content="Hello",
        ),
    ]


@pytest.mark.asyncio
async def test_tracked_provider_returns_original_response() -> None:
    """The wrapper should return the provider's original response."""

    response = build_response()

    provider = FakeLLMProvider(
        response=response,
    )

    recorder = AsyncMock()

    tracked = TrackedLLMProvider(
        provider=provider,
        user_id=uuid4(),
        operation=ModelRunOperation.QUERY,
        provider_name="ollama",
        recorder=recorder,
    )

    result = await tracked.generate(
        build_messages(),
        temperature=0.0,
    )

    assert result is response
    recorder.record_completed.assert_awaited_once()


@pytest.mark.asyncio
async def test_tracked_provider_records_success() -> None:
    """A successful generation should produce completed telemetry."""

    response = build_response()

    provider = FakeLLMProvider(
        response=response,
    )

    recorder = AsyncMock()

    user_id = uuid4()

    tracked = TrackedLLMProvider(
        provider=provider,
        user_id=user_id,
        operation=ModelRunOperation.QUERY,
        provider_name="ollama",
        recorder=recorder,
    )

    await tracked.generate(
        build_messages(),
        temperature=0.2,
    )

    recorder.record_completed.assert_awaited_once()

    call = recorder.record_completed.await_args

    assert call.kwargs["user_id"] == user_id
    assert call.kwargs["operation"] == ModelRunOperation.QUERY
    assert call.kwargs["provider"] == "ollama"
    assert call.kwargs["temperature"] == 0.2
    assert call.kwargs["response"] is response
    assert isinstance(
        call.kwargs["started_at"],
        datetime,
    )
    assert call.kwargs["latency_ms"] >= 0.0


@pytest.mark.asyncio
async def test_tracked_provider_records_token_usage() -> None:
    """The original response, including usage, should be passed to the recorder."""

    usage = TokenUsage(
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
    )

    response = build_response(
        usage=usage,
    )

    provider = FakeLLMProvider(
        response=response,
    )

    recorder = AsyncMock()

    tracked = TrackedLLMProvider(
        provider=provider,
        user_id=uuid4(),
        operation=ModelRunOperation.QUERY,
        provider_name="ollama",
        recorder=recorder,
    )

    await tracked.generate(
        build_messages(),
    )

    recorder.record_completed.assert_awaited_once()

    recorded_response = (
        recorder.record_completed.await_args.kwargs["response"]
    )

    assert recorded_response.usage == usage
    assert recorded_response.usage.prompt_tokens == 10
    assert recorded_response.usage.completion_tokens == 20
    assert recorded_response.usage.total_tokens == 30


@pytest.mark.asyncio
async def test_tracked_provider_records_failure() -> None:
    """A provider failure should produce failed telemetry."""

    error = TimeoutError(
        "LLM request timed out",
    )

    provider = FakeLLMProvider(
        error=error,
    )

    recorder = AsyncMock()

    user_id = uuid4()

    tracked = TrackedLLMProvider(
        provider=provider,
        user_id=user_id,
        operation=ModelRunOperation.QUERY,
        provider_name="ollama",
        recorder=recorder,
    )

    with pytest.raises(
        TimeoutError,
        match="LLM request timed out",
    ):
        await tracked.generate(
            build_messages(),
        )

    recorder.record_failed.assert_awaited_once()

    call = recorder.record_failed.await_args

    assert call.kwargs["user_id"] == user_id
    assert call.kwargs["operation"] == ModelRunOperation.QUERY
    assert call.kwargs["provider"] == "ollama"
    assert call.kwargs["temperature"] == 0.0
    assert call.kwargs["error"] is error
    assert isinstance(
        call.kwargs["started_at"],
        datetime,
    )
    assert call.kwargs["latency_ms"] >= 0.0


@pytest.mark.asyncio
async def test_tracked_provider_reraises_original_exception() -> None:
    """The wrapper must not replace the original provider exception."""

    error = RuntimeError(
        "provider unavailable",
    )

    provider = FakeLLMProvider(
        error=error,
    )

    recorder = AsyncMock()

    tracked = TrackedLLMProvider(
        provider=provider,
        user_id=uuid4(),
        operation=ModelRunOperation.QUERY,
        provider_name="ollama",
        recorder=recorder,
    )

    with pytest.raises(RuntimeError) as exc_info:
        await tracked.generate(
            build_messages(),
        )

    assert exc_info.value is error
    recorder.record_failed.assert_awaited_once()


@pytest.mark.asyncio
async def test_tracker_failure_does_not_mask_success() -> None:
    """Telemetry failure must not prevent a successful LLM response."""

    response = build_response()

    provider = FakeLLMProvider(
        response=response,
    )

    recorder = AsyncMock()

    recorder.record_completed.side_effect = RuntimeError(
        "telemetry database unavailable",
    )

    tracked = TrackedLLMProvider(
        provider=provider,
        user_id=uuid4(),
        operation=ModelRunOperation.QUERY,
        provider_name="ollama",
        recorder=recorder,
    )

    result = await tracked.generate(
        build_messages(),
    )

    assert result is response
    recorder.record_completed.assert_awaited_once()


@pytest.mark.asyncio
async def test_tracker_failure_does_not_mask_llm_failure() -> None:
    """Telemetry failure must not replace the original LLM failure."""

    llm_error = RuntimeError(
        "LLM unavailable",
    )

    provider = FakeLLMProvider(
        error=llm_error,
    )

    recorder = AsyncMock()

    recorder.record_failed.side_effect = RuntimeError(
        "telemetry database unavailable",
    )

    tracked = TrackedLLMProvider(
        provider=provider,
        user_id=uuid4(),
        operation=ModelRunOperation.QUERY,
        provider_name="ollama",
        recorder=recorder,
    )

    with pytest.raises(RuntimeError) as exc_info:
        await tracked.generate(
            build_messages(),
        )

    assert exc_info.value is llm_error
    recorder.record_failed.assert_awaited_once()