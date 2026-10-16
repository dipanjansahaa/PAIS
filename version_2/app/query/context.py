"""Context construction for grounded query generation."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from app.retrieval.models import RetrievalResult


@dataclass(frozen=True, slots=True)
class ContextChunk:
    """A retrieved chunk prepared for model context."""

    citation_id: str
    chunk_id: str
    document_id: str
    content: str
    similarity: float
    metadata: dict | None


@dataclass(frozen=True, slots=True)
class ContextSource:
    """A source document represented by one or more chunks."""

    citation_id: str
    document_id: str
    chunks: tuple[ContextChunk, ...]


@dataclass(frozen=True, slots=True)
class QueryContext:
    """Model-ready context and its provenance mapping."""

    text: str
    sources: tuple[ContextSource, ...]
    estimated_tokens: int
    truncated: bool


class ContextBuilder:
    """Build deterministic, provenance-aware LLM context."""

    def __init__(
        self,
        *,
        max_context_tokens: int = 3000,
    ) -> None:
        if max_context_tokens <= 0:
            raise ValueError(
                "max_context_tokens must be greater than zero."
            )

        self.max_context_tokens = max_context_tokens

    def build(
        self,
        results: list[RetrievalResult],
    ) -> QueryContext:
        """Build model-ready context from retrieval results."""

        if not results:
            return QueryContext(
                text="",
                sources=(),
                estimated_tokens=0,
                truncated=False,
            )

        unique_results = self._deduplicate(results)

        grouped_sources = self._group_by_document(unique_results)

        selected_sources: list[ContextSource] = []
        selected_chunks: list[ContextChunk] = []

        estimated_tokens = 0
        truncated = False

        for source_index, (document_id, chunks) in enumerate(
            grouped_sources.items(),
            start=1,
        ):
            citation_id = f"S{source_index}"

            source_chunks: list[ContextChunk] = []

            for chunk_index, result in enumerate(chunks, start=1):
                chunk_citation_id = f"{citation_id}-C{chunk_index}"

                context_chunk = ContextChunk(
                    citation_id=chunk_citation_id,
                    chunk_id=str(result.chunk_id),
                    document_id=str(result.document_id),
                    content=result.content,
                    similarity=result.similarity,
                    metadata=result.metadata,
                )

                chunk_tokens = self._estimate_tokens(
                    result.content
                )

                if (
                    estimated_tokens + chunk_tokens
                    > self.max_context_tokens
                ):
                    truncated = True
                    break

                source_chunks.append(context_chunk)
                selected_chunks.append(context_chunk)
                estimated_tokens += chunk_tokens

            if source_chunks:
                selected_sources.append(
                    ContextSource(
                        citation_id=citation_id,
                        document_id=document_id,
                        chunks=tuple(source_chunks),
                    )
                )

            if truncated:
                break

        text = self._format_context(selected_sources)

        return QueryContext(
            text=text,
            sources=tuple(selected_sources),
            estimated_tokens=estimated_tokens,
            truncated=truncated,
        )

    @staticmethod
    def _deduplicate(
        results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        """Remove duplicate chunks while preserving retrieval order."""

        seen_chunk_ids: set[str] = set()
        unique_results: list[RetrievalResult] = []

        for result in results:
            chunk_id = str(result.chunk_id)

            if chunk_id in seen_chunk_ids:
                continue

            seen_chunk_ids.add(chunk_id)
            unique_results.append(result)

        return unique_results

    @staticmethod
    def _group_by_document(
        results: list[RetrievalResult],
    ) -> dict[str, list[RetrievalResult]]:
        """Group chunks by document while preserving retrieval order."""

        grouped: dict[str, list[RetrievalResult]] = {}

        for result in results:
            document_id = str(result.document_id)

            grouped.setdefault(document_id, []).append(result)

        return grouped

    @staticmethod
    def _estimate_tokens(content: str) -> int:
        """Estimate token usage without introducing a tokenizer dependency."""

        if not content:
            return 0

        return ceil(len(content) / 4)

    @staticmethod
    def _format_context(
        sources: list[ContextSource],
    ) -> str:
        """Format grouped sources into deterministic model context."""

        sections: list[str] = []

        for source in sources:
            chunk_sections = []

            for chunk in source.chunks:
                chunk_sections.append(
                    f"[{chunk.citation_id}]\n"
                    f"{chunk.content}"
                )

            sections.append(
                f"[{source.citation_id}]\n"
                + "\n\n".join(chunk_sections)
            )

        return "\n\n".join(sections)