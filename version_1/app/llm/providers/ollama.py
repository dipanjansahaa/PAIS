"""Ollama implementation of the PAIS LLM provider interface."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from ollama import AsyncClient

from app.llm.base import LLMProvider
from app.llm.models import LLMResponse, Message, TokenUsage


class OllamaProvider(LLMProvider):
    """LLM provider backed by a local or remote Ollama server."""

    def __init__(
        self,
        model: str,
        base_url: str,
        timeout: float,
    ) -> None:
        model = model.strip()
        base_url = base_url.strip()

        if not model:
            raise ValueError("LLM model must not be empty.")

        if not base_url:
            raise ValueError("LLM base URL must not be empty.")

        if timeout <= 0:
            raise ValueError("LLM timeout must be greater than zero.")

        self._model = model
        self._base_url = base_url
        self._timeout = timeout

        self._client = AsyncClient(
            host=base_url,
            timeout=timeout,
        )

    async def generate(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        response_schema: type | None = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Generate a response using Ollama."""

        if not messages:
            raise ValueError("Messages must not be empty.")

        if temperature < 0:
            raise ValueError("Temperature must not be negative.")

        ollama_messages = [
            {
                "role": message.role,
                "content": message.content,
            }
            for message in messages
        ]

        request_kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        if json_mode:
            request_kwargs["format"] = "json"
        elif response_schema is not None:
            request_kwargs["format"] = response_schema.model_json_schema()

        started_at = perf_counter()

        response = await self._client.chat(**request_kwargs)

        latency_ms = (perf_counter() - started_at) * 1000

        usage = self._build_usage(response)

        return LLMResponse(
            content=response.message.content,
            model=response.model,
            usage=usage,
            latency_ms=latency_ms,
            finish_reason=response.done_reason or None,
        )

    @staticmethod
    def _build_usage(response: Any) -> TokenUsage | None:
        """Normalize Ollama token usage metadata."""

        prompt_tokens = response.prompt_eval_count
        completion_tokens = response.eval_count

        if prompt_tokens is None or completion_tokens is None:
            return None

        return TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )