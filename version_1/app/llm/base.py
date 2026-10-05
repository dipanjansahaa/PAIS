"""Interfaces for large language model providers."""

from __future__ import annotations

from typing import Protocol

from app.llm.models import LLMResponse, Message


class LLMProvider(Protocol):
    """Provider-independent interface for text generation."""

    async def generate(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        response_schema: type | None = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Generate a response from the supplied messages."""
        ...