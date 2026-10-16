"""Models used by the LLM provider abstraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


MessageRole = Literal["system", "user", "assistant"]


@dataclass(frozen=True, slots=True)
class Message:
    """A single message exchanged with an LLM."""

    role: MessageRole
    content: str


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Token usage reported by an LLM provider."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Provider-independent normalized LLM response."""

    content: str
    model: str
    usage: TokenUsage | None
    latency_ms: float
    finish_reason: str | None