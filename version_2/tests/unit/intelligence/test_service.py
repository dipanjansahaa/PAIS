"""Tests for structured intelligence extraction."""

from uuid import uuid4

import pytest

from datetime import datetime, timezone

from app.intelligence.models import (
    IntelligenceSource,
    StructuredIntelligence,
    TaskCandidate,
    DecisionCandidate,
)
from app.intelligence.service import (
    IntelligenceExtractionService,
)
from app.llm.models import LLMResponse
from app.retrieval.models import RetrievalResult


class FakeStructuredLLM:
    """Deterministic structured LLM for extraction tests."""

    def __init__(
        self,
        intelligence: StructuredIntelligence,
    ) -> None:
        self.intelligence = intelligence
        self.messages = []
        self.schema = None
        self.temperature = None

    async def generate(
        self,
        messages,
        *,
        schema,
        temperature=0.0,
    ):
        self.messages.append(messages)
        self.schema = schema
        self.temperature = temperature

        return (
            self.intelligence,
            LLMResponse(
                content="{}",
                model="test-model",
                usage=None,
                latency_ms=10.0,
                finish_reason="stop",
            ),
        )


def create_result(
    *,
    chunk_id=None,
    content="The API review must be completed.",
):
    """Create a retrieval result for tests."""

    return RetrievalResult(
        chunk_id=chunk_id or uuid4(),
        document_id=uuid4(),
        content=content,
        similarity=0.95,
        metadata=None,
    )


@pytest.mark.asyncio
async def test_extraction_returns_empty_result_for_no_sources():
    """No retrieved sources should produce empty intelligence."""

    llm = FakeStructuredLLM(
        StructuredIntelligence(
            tasks=[],
        ),
    )

    service = IntelligenceExtractionService(
        structured_llm=llm,
    )

    result = await service.extract([])

    assert result.intelligence == StructuredIntelligence()
    assert result.model is None
    assert result.latency_ms is None
    assert llm.messages == []


@pytest.mark.asyncio
async def test_extraction_builds_grounded_prompt():
    """The extraction prompt should contain supplied chunk IDs and content."""

    chunk_id = uuid4()

    retrieval_result = create_result(
        chunk_id=chunk_id,
        content="Review the API before Friday.",
    )

    intelligence = StructuredIntelligence(
        tasks=[
            TaskCandidate(
                description="Review the API",
                sources=[
                    IntelligenceSource(
                        chunk_id=chunk_id,
                    ),
                ],
            ),
        ],
    )

    llm = FakeStructuredLLM(intelligence)

    service = IntelligenceExtractionService(
        structured_llm=llm,
    )

    await service.extract([retrieval_result])

    assert len(llm.messages) == 1

    messages = llm.messages[0]

    assert messages[0].role == "system"
    assert "structured intelligence" in (
        messages[0].content.lower()
    )

    assert messages[1].role == "user"
    assert str(chunk_id) in messages[1].content
    assert "Review the API before Friday." in messages[1].content


@pytest.mark.asyncio
async def test_extraction_passes_structured_schema_to_provider():
    """Extraction should request StructuredIntelligence validation."""

    retrieval_result = create_result()

    llm = FakeStructuredLLM(
        StructuredIntelligence(),
    )

    service = IntelligenceExtractionService(
        structured_llm=llm,
    )

    await service.extract([retrieval_result])

    assert llm.schema is StructuredIntelligence


@pytest.mark.asyncio
async def test_extraction_passes_temperature():
    """Extraction temperature should reach the structured provider."""

    retrieval_result = create_result()

    llm = FakeStructuredLLM(
        StructuredIntelligence(),
    )

    service = IntelligenceExtractionService(
        structured_llm=llm,
    )

    await service.extract(
        [retrieval_result],
        temperature=0.2,
    )

    assert llm.temperature == 0.2


@pytest.mark.asyncio
async def test_extraction_preserves_response_metadata():
    """Provider metadata should be exposed by the extraction result."""

    retrieval_result = create_result()

    llm = FakeStructuredLLM(
        StructuredIntelligence(),
    )

    service = IntelligenceExtractionService(
        structured_llm=llm,
    )

    result = await service.extract(
        [retrieval_result],
    )

    assert result.model == "test-model"
    assert result.latency_ms == 10.0


@pytest.mark.asyncio
async def test_extraction_validates_provenance():
    """Every extracted source must reference a supplied chunk."""

    supplied_chunk_id = uuid4()
    unknown_chunk_id = uuid4()

    retrieval_result = create_result(
        chunk_id=supplied_chunk_id,
    )

    intelligence = StructuredIntelligence(
        tasks=[
            TaskCandidate(
                description="Review the API",
                sources=[
                    IntelligenceSource(
                        chunk_id=unknown_chunk_id,
                    ),
                ],
            ),
        ],
    )

    llm = FakeStructuredLLM(intelligence)

    service = IntelligenceExtractionService(
        structured_llm=llm,
    )

    with pytest.raises(
        ValueError,
        match="unknown source chunk ID",
    ):
        await service.extract(
            [retrieval_result],
        )


@pytest.mark.asyncio
async def test_extraction_accepts_valid_provenance():
    """Sources referencing retrieved chunks should be accepted."""

    chunk_id = uuid4()

    retrieval_result = create_result(
        chunk_id=chunk_id,
    )

    intelligence = StructuredIntelligence(
        tasks=[
            TaskCandidate(
                description="Review the API",
                sources=[
                    IntelligenceSource(
                        chunk_id=chunk_id,
                    ),
                ],
            ),
        ],
    )

    llm = FakeStructuredLLM(intelligence)

    service = IntelligenceExtractionService(
        structured_llm=llm,
    )

    result = await service.extract(
        [retrieval_result],
    )

    assert len(result.intelligence.tasks) == 1
    assert (
        result.intelligence.tasks[0].sources[0].chunk_id
        == chunk_id
    )


@pytest.mark.asyncio
async def test_extraction_preserves_multiple_source_chunks():
    """An extraction may legitimately cite multiple retrieved chunks."""

    chunk_a = uuid4()
    chunk_b = uuid4()

    results = [
        create_result(
            chunk_id=chunk_a,
            content="The deployment is scheduled for Monday.",
        ),
        create_result(
            chunk_id=chunk_b,
            content="The team must complete testing before deployment.",
        ),
    ]

    intelligence = StructuredIntelligence(
        tasks=[
            TaskCandidate(
                description="Complete testing before deployment",
                sources=[
                    IntelligenceSource(chunk_id=chunk_a),
                    IntelligenceSource(chunk_id=chunk_b),
                ],
            ),
        ],
    )

    llm = FakeStructuredLLM(intelligence)

    service = IntelligenceExtractionService(
        structured_llm=llm,
    )

    result = await service.extract(results)

    assert len(result.intelligence.tasks) == 1
    assert {
        source.chunk_id
        for source in result.intelligence.tasks[0].sources
    } == {chunk_a, chunk_b}


@pytest.mark.asyncio
async def test_extraction_deduplicates_duplicate_tasks():
    """Duplicate tasks should be merged by the extraction service."""

    chunk_id_1 = uuid4()
    chunk_id_2 = uuid4()

    results = [
        create_result(
            chunk_id=chunk_id_1,
            content="Alice must send the project report.",
        ),
        create_result(
            chunk_id=chunk_id_2,
            content="Alice needs to send the project report.",
        ),
    ]

    intelligence = StructuredIntelligence(
        tasks=[
            TaskCandidate(
                description="Send the project report",
                owner="Alice",
                sources=[
                    IntelligenceSource(chunk_id=chunk_id_1),
                ],
            ),
            TaskCandidate(
                description="  send   the PROJECT report  ",
                owner="alice",
                sources=[
                    IntelligenceSource(chunk_id=chunk_id_2),
                ],
            ),
        ],
    )

    llm = FakeStructuredLLM(intelligence)

    service = IntelligenceExtractionService(
        structured_llm=llm,
    )

    result = await service.extract(results)

    assert len(result.intelligence.tasks) == 1

    task = result.intelligence.tasks[0]

    assert task.description == "Send the project report"
    assert task.owner == "Alice"

    assert [source.chunk_id for source in task.sources] == [
        chunk_id_1,
        chunk_id_2,
    ]


@pytest.mark.asyncio
async def test_extraction_deduplicates_duplicate_decisions():
    """Duplicate decisions should be merged by the extraction service."""

    chunk_id_1 = uuid4()
    chunk_id_2 = uuid4()

    results = [
        create_result(
            chunk_id=chunk_id_1,
            content="The team decided to use PostgreSQL.",
        ),
        create_result(
            chunk_id=chunk_id_2,
            content="The database decision was PostgreSQL.",
        ),
    ]

    intelligence = StructuredIntelligence(
        decisions=[
            DecisionCandidate(
                title="Database choice",
                description="Use PostgreSQL",
                sources=[
                    IntelligenceSource(chunk_id=chunk_id_1),
                ],
            ),
            DecisionCandidate(
                title=" database   choice ",
                description=" use PostgreSQL ",
                sources=[
                    IntelligenceSource(chunk_id=chunk_id_2),
                ],
            ),
        ],
    )

    llm = FakeStructuredLLM(intelligence)

    service = IntelligenceExtractionService(
        structured_llm=llm,
    )

    result = await service.extract(results)

    assert len(result.intelligence.decisions) == 1

    decision = result.intelligence.decisions[0]

    assert decision.title == "Database choice"
    assert decision.description == "Use PostgreSQL"

    assert [source.chunk_id for source in decision.sources] == [
        chunk_id_1,
        chunk_id_2,
    ]


@pytest.mark.asyncio
async def test_extraction_preserves_conflicting_tasks():
    """Tasks with conflicting due dates should remain separate."""

    chunk_id_1 = uuid4()
    chunk_id_2 = uuid4()

    due_at_1 = datetime(2026, 10, 1, tzinfo=timezone.utc)
    due_at_2 = datetime(2026, 10, 5, tzinfo=timezone.utc)

    results = [
        create_result(
            chunk_id=chunk_id_1,
            content="Alice must submit the report on October 1.",
        ),
        create_result(
            chunk_id=chunk_id_2,
            content="Alice must submit the report on October 5.",
        ),
    ]

    intelligence = StructuredIntelligence(
        tasks=[
            TaskCandidate(
                description="Submit the report",
                owner="Alice",
                due_at=due_at_1,
                sources=[
                    IntelligenceSource(chunk_id=chunk_id_1),
                ],
            ),
            TaskCandidate(
                description="submit the report",
                owner="alice",
                due_at=due_at_2,
                sources=[
                    IntelligenceSource(chunk_id=chunk_id_2),
                ],
            ),
        ],
    )

    llm = FakeStructuredLLM(intelligence)

    service = IntelligenceExtractionService(
        structured_llm=llm,
    )

    result = await service.extract(results)

    assert len(result.intelligence.tasks) == 2

    assert {
        task.due_at
        for task in result.intelligence.tasks
    } == {
        due_at_1,
        due_at_2,
    }