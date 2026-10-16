"""Tests for the Ollama LLM provider."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.llm.models import Message
from app.llm.providers.ollama import OllamaProvider

from pydantic import BaseModel


class ExampleSchema(BaseModel):
    """Schema used to test Ollama structured output."""

    name: str


def test_ollama_provider_rejects_empty_model():
    """Provider should reject an empty model name."""

    with pytest.raises(ValueError, match="model must not be empty"):
        OllamaProvider(
            model="",
            base_url="http://localhost:11434",
            timeout=60.0,
        )


def test_ollama_provider_rejects_empty_base_url():
    """Provider should reject an empty base URL."""

    with pytest.raises(ValueError, match="base URL must not be empty"):
        OllamaProvider(
            model="test-model",
            base_url="",
            timeout=60.0,
        )


@pytest.mark.parametrize("timeout", [0, -1])
def test_ollama_provider_rejects_invalid_timeout(timeout):
    """Provider should reject non-positive timeouts."""

    with pytest.raises(
        ValueError,
        match="timeout must be greater than zero",
    ):
        OllamaProvider(
            model="test-model",
            base_url="http://localhost:11434",
            timeout=timeout,
        )


async def test_ollama_provider_generates_response():
    """Provider should generate and normalize an Ollama response."""

    provider = OllamaProvider(
        model="test-model",
        base_url="http://localhost:11434",
        timeout=60.0,
    )

    response = SimpleNamespace(
        model="test-model",
        message=SimpleNamespace(
            content="This is the generated answer.",
        ),
        prompt_eval_count=10,
        eval_count=5,
        done_reason="stop",
    )

    provider._client.chat = AsyncMock(return_value=response)

    result = await provider.generate(
        [
            Message(
                role="user",
                content="What is PAIS?",
            )
        ]
    )

    assert result.content == "This is the generated answer."
    assert result.model == "test-model"
    assert result.finish_reason == "stop"
    assert result.usage is not None
    assert result.usage.prompt_tokens == 10
    assert result.usage.completion_tokens == 5
    assert result.usage.total_tokens == 15
    assert result.latency_ms >= 0


async def test_ollama_provider_normalizes_token_usage():
    """Provider should normalize Ollama token counts."""

    provider = OllamaProvider(
        model="test-model",
        base_url="http://localhost:11434",
        timeout=60.0,
    )

    response = SimpleNamespace(
        model="test-model",
        message=SimpleNamespace(content="Answer"),
        prompt_eval_count=25,
        eval_count=15,
        done_reason="stop",
    )

    provider._client.chat = AsyncMock(return_value=response)

    result = await provider.generate(
        [Message(role="user", content="Question")]
    )

    assert result.usage is not None
    assert result.usage.prompt_tokens == 25
    assert result.usage.completion_tokens == 15
    assert result.usage.total_tokens == 40


async def test_ollama_provider_handles_missing_usage():
    """Provider should handle missing token usage metadata."""

    provider = OllamaProvider(
        model="test-model",
        base_url="http://localhost:11434",
        timeout=60.0,
    )

    response = SimpleNamespace(
        model="test-model",
        message=SimpleNamespace(content="Answer"),
        prompt_eval_count=None,
        eval_count=None,
        done_reason=None,
    )

    provider._client.chat = AsyncMock(return_value=response)

    result = await provider.generate(
        [Message(role="user", content="Question")]
    )

    assert result.usage is None
    assert result.finish_reason is None


async def test_ollama_provider_passes_temperature():
    """Provider should pass the requested temperature to Ollama."""

    provider = OllamaProvider(
        model="test-model",
        base_url="http://localhost:11434",
        timeout=60.0,
    )

    response = SimpleNamespace(
        model="test-model",
        message=SimpleNamespace(content="Answer"),
        prompt_eval_count=10,
        eval_count=5,
        done_reason="stop",
    )

    provider._client.chat = AsyncMock(return_value=response)

    await provider.generate(
        [Message(role="user", content="Question")],
        temperature=0.7,
    )

    provider._client.chat.assert_awaited_once()

    call_kwargs = provider._client.chat.call_args.kwargs

    assert call_kwargs["options"]["temperature"] == 0.7
    assert call_kwargs["stream"] is False
    assert call_kwargs["model"] == "test-model"


async def test_ollama_provider_rejects_empty_messages():
    """Provider should reject an empty message list."""

    provider = OllamaProvider(
        model="test-model",
        base_url="http://localhost:11434",
        timeout=60.0,
    )

    with pytest.raises(ValueError, match="Messages must not be empty"):
        await provider.generate([])


async def test_ollama_provider_rejects_negative_temperature():
    """Provider should reject a negative temperature."""

    provider = OllamaProvider(
        model="test-model",
        base_url="http://localhost:11434",
        timeout=60.0,
    )

    with pytest.raises(ValueError, match="Temperature must not be negative"):
        await provider.generate(
            [Message(role="user", content="Question")],
            temperature=-0.1,
        )


async def test_ollama_provider_uses_json_mode():
    """Provider should request generic JSON output when json_mode is enabled."""

    provider = OllamaProvider(
        model="test-model",
        base_url="http://localhost:11434",
        timeout=60.0,
    )

    response = SimpleNamespace(
        model="test-model",
        message=SimpleNamespace(content='{"name": "test"}'),
        prompt_eval_count=10,
        eval_count=5,
        done_reason="stop",
    )

    provider._client.chat = AsyncMock(return_value=response)

    await provider.generate(
        [Message(role="user", content="Return JSON")],
        json_mode=True,
    )

    provider._client.chat.assert_awaited_once()

    call_kwargs = provider._client.chat.call_args.kwargs

    assert call_kwargs["format"] == "json"


async def test_ollama_provider_uses_response_schema():
    """Provider should pass the Pydantic schema to Ollama."""

    provider = OllamaProvider(
        model="test-model",
        base_url="http://localhost:11434",
        timeout=60.0,
    )

    response = SimpleNamespace(
        model="test-model",
        message=SimpleNamespace(
            content='{"name": "test"}',
        ),
        prompt_eval_count=10,
        eval_count=5,
        done_reason="stop",
    )

    provider._client.chat = AsyncMock(return_value=response)

    await provider.generate(
        [Message(role="user", content="Return structured JSON")],
        response_schema=ExampleSchema,
    )

    provider._client.chat.assert_awaited_once()

    call_kwargs = provider._client.chat.call_args.kwargs

    assert call_kwargs["format"] == ExampleSchema.model_json_schema()