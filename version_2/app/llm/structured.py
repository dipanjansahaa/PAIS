"""Structured LLM generation and validation."""

from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.llm.base import LLMProvider
from app.llm.models import LLMResponse, Message


StructuredModel = TypeVar(
    "StructuredModel",
    bound=BaseModel,
)


class StructuredLLMError(RuntimeError):
    """Raised when structured LLM output cannot be validated."""


class StructuredLLMProvider:
    """Validate LLM responses against Pydantic schemas."""

    def __init__(
        self,
        provider: LLMProvider,
    ) -> None:
        self.provider = provider

    async def generate(
        self,
        messages: list[Message],
        *,
        schema: type[StructuredModel],
        temperature: float = 0.0,
        json_mode: bool = False,
    ) -> tuple[StructuredModel, LLMResponse]:
        """Generate and validate structured LLM output."""

        response = await self.provider.generate(
            messages,
            temperature=temperature,
            response_schema=schema,
            json_mode=json_mode,
        )

        try:
            payload = json.loads(response.content)
        except json.JSONDecodeError as exc:
            raise StructuredLLMError(
                "LLM returned invalid JSON."
            ) from exc

        try:
            result = schema.model_validate(payload)
        except ValidationError as exc:
            raise StructuredLLMError(
                "LLM response failed schema validation."
            ) from exc

        return result, response