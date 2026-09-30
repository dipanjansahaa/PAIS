"""Tests for structured LLM generation."""

from dataclasses import dataclass
from uuid import uuid4

import pytest
from pydantic import BaseModel, Field

from app.llm.models import LLMResponse
from app.llm.structured import (
    StructuredLLMError,
    StructuredLLMProvider,
)


class ExampleSchema(BaseModel):
    """Schema used by structured generation tests."""

    name: str = Field(min_length=1)
    value: int


@dataclass
class FakeLLMProvider:
    """Deterministic provider for structured generation tests."""

    content: str

    async def generate(
        self,
        messages,
        *,
        temperature=0.0,
        response_schema=None,
    ):
        return LLMResponse(
            content=self.content,
            model="test-model",
            usage=None,
            latency_ms=1.0,
            finish_reason="stop",
        )


@pytest.mark.asyncio
async def test_structured_provider_validates_response():
    """Valid JSON should become the requested Pydantic model."""

    provider = StructuredLLMProvider(
        FakeLLMProvider(
            content='{"name": "test", "value": 42}',
        ),
    )

    result, response = await provider.generate(
        [],
        schema=ExampleSchema,
    )

    assert result.name == "test"
    assert result.value == 42
    assert response.model == "test-model"


@pytest.mark.asyncio
async def test_structured_provider_passes_schema_to_llm():
    """The requested schema should be passed to the provider."""

    class TrackingProvider:
        def __init__(self):
            self.schema = None

        async def generate(
            self,
            messages,
            *,
            temperature=0.0,
            response_schema=None,
        ):
            self.schema = response_schema

            return LLMResponse(
                content='{"name": "test", "value": 42}',
                model="test-model",
                usage=None,
                latency_ms=1.0,
                finish_reason="stop",
            )

    provider = TrackingProvider()

    structured = StructuredLLMProvider(provider)

    await structured.generate(
        [],
        schema=ExampleSchema,
    )

    assert provider.schema is ExampleSchema


@pytest.mark.asyncio
async def test_structured_provider_rejects_invalid_json():
    """Invalid JSON must fail explicitly."""

    provider = StructuredLLMProvider(
        FakeLLMProvider(
            content="not valid json",
        ),
    )

    with pytest.raises(
        StructuredLLMError,
        match="invalid JSON",
    ):
        await provider.generate(
            [],
            schema=ExampleSchema,
        )


@pytest.mark.asyncio
async def test_structured_provider_rejects_schema_violation():
    """Valid JSON that violates the schema must fail."""

    provider = StructuredLLMProvider(
        FakeLLMProvider(
            content='{"name": "", "value": "wrong"}',
        ),
    )

    with pytest.raises(
        StructuredLLMError,
        match="schema validation",
    ):
        await provider.generate(
            [],
            schema=ExampleSchema,
        )