"""Models used by the query application service."""

from __future__ import annotations

from dataclasses import dataclass

from app.llm.models import LLMResponse
from app.query.context import ContextSource


@dataclass(frozen=True, slots=True)
class QueryResult:
    """Final internal result produced by QueryService."""

    query: str
    answer: str
    sources: tuple[ContextSource, ...]
    model: str | None
    latency_ms: float | None
    truncated: bool