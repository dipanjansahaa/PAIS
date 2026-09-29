"""Tests for LLM provider models."""

from app.llm.models import LLMResponse, Message, TokenUsage


def test_message_stores_role_and_content():
    message = Message(
        role="user",
        content="What is PAIS?",
    )

    assert message.role == "user"
    assert message.content == "What is PAIS?"


def test_token_usage_stores_token_counts():
    usage = TokenUsage(
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
    )

    assert usage.prompt_tokens == 10
    assert usage.completion_tokens == 20
    assert usage.total_tokens == 30


def test_llm_response_stores_normalized_response_metadata():
    usage = TokenUsage(
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
    )

    response = LLMResponse(
        content="PAIS is a personal intelligence system.",
        model="test-model",
        usage=usage,
        latency_ms=125.5,
        finish_reason="stop",
    )

    assert response.content == "PAIS is a personal intelligence system."
    assert response.model == "test-model"
    assert response.usage == usage
    assert response.latency_ms == 125.5
    assert response.finish_reason == "stop"


def test_llm_response_allows_missing_usage():
    response = LLMResponse(
        content="Answer",
        model="test-model",
        usage=None,
        latency_ms=50.0,
        finish_reason=None,
    )

    assert response.usage is None
    assert response.finish_reason is None