"""Structured intelligence extraction service."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.intelligence.models import StructuredIntelligence
from app.llm.models import LLMResponse, Message
from app.llm.structured import StructuredLLMProvider
from app.retrieval.models import RetrievalResult
from app.intelligence.deduplication import deduplicate_intelligence


EXTRACTION_SYSTEM_PROMPT = """\
You are the structured intelligence extraction component of PAIS.

Extract only information explicitly supported by the supplied source chunks.

The available categories are:
- tasks
- commitments
- decisions
- projects
- people
- risks
- follow_ups
- deadlines

Rules:
- Do not invent information.
- Do not infer facts that are not explicitly supported.
- Every extracted item must contain at least one source chunk ID.
- Only use source chunk IDs that appear in the supplied sources.
- If a category has no supported information, return an empty list.
- Preserve uncertainty instead of converting uncertain information into facts.
- Keep descriptions concise and faithful to the source.
- Do not create duplicate items from the same evidence.
"""


@dataclass(frozen=True, slots=True)
class IntelligenceExtractionResult:
    """Result of a structured intelligence extraction."""

    intelligence: StructuredIntelligence
    model: str | None
    latency_ms: float | None


class IntelligenceExtractionService:
    """Extract structured intelligence from retrieved source chunks."""

    def __init__(
        self,
        *,
        structured_llm: StructuredLLMProvider,
    ) -> None:
        self.structured_llm = structured_llm

    async def extract(
        self,
        results: list[RetrievalResult],
        *,
        temperature: float = 0.0,
    ) -> IntelligenceExtractionResult:
        """Extract structured intelligence from retrieval results."""

        if not results:
            return IntelligenceExtractionResult(
                intelligence=StructuredIntelligence(),
                model=None,
                latency_ms=None,
            )

        messages = self._build_messages(results)

        intelligence, response = await self.structured_llm.generate(
            messages,
            schema=StructuredIntelligence,
            temperature=temperature,
        )

        self._validate_provenance(
            intelligence=intelligence,
            results=results,
        )

        intelligence = deduplicate_intelligence(intelligence)

        return IntelligenceExtractionResult(
            intelligence=intelligence,
            model=response.model,
            latency_ms=response.latency_ms,
        )

    @staticmethod
    def _build_messages(
        results: list[RetrievalResult],
    ) -> list[Message]:
        """Build the structured extraction prompt."""

        source_sections: list[str] = []

        for result in results:
            source_sections.append(
                f"[CHUNK_ID: {result.chunk_id}]\n"
                f"{result.content}"
            )

        sources = "\n\n".join(source_sections)

        user_prompt = (
            "SOURCE CHUNKS:\n"
            f"{sources}\n\n"
            "Extract all supported structured intelligence "
            "from these sources."
        )

        return [
            Message(
                role="system",
                content=EXTRACTION_SYSTEM_PROMPT,
            ),
            Message(
                role="user",
                content=user_prompt,
            ),
        ]

    @staticmethod
    def _validate_provenance(
        *,
        intelligence: StructuredIntelligence,
        results: list[RetrievalResult],
    ) -> None:
        """Ensure extracted provenance references supplied chunks only."""

        valid_chunk_ids = {
            result.chunk_id
            for result in results
        }

        for source in IntelligenceExtractionService._iter_sources(
            intelligence
        ):
            if source.chunk_id not in valid_chunk_ids:
                raise ValueError(
                    "Structured intelligence contains an unknown "
                    f"source chunk ID: {source.chunk_id}"
                )

    @staticmethod
    def _iter_sources(
        intelligence: StructuredIntelligence,
    ):
        """Yield every provenance source in the extraction."""

        for item in intelligence.tasks:
            yield from item.sources

        for item in intelligence.commitments:
            yield from item.sources

        for item in intelligence.decisions:
            yield from item.sources

        for item in intelligence.projects:
            yield from item.sources

        for item in intelligence.people:
            yield from item.sources

        for item in intelligence.risks:
            yield from item.sources

        for item in intelligence.follow_ups:
            yield from item.sources

        for item in intelligence.deadlines:
            yield from item.sources