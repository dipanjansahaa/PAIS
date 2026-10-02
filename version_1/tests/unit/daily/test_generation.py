"""Tests for daily intelligence generation."""

from datetime import datetime
from uuid import uuid4

import pytest
from app.llm.models import LLMResponse

from app.daily.context import DailyIntelligenceContext
from app.daily.enrichment import (
    DailyPersonContext,
    DailyProjectContext,
    DailyRiskContext,
)
from app.daily.generation import (
    DailyBrief,
    DailyGenerationService,
)
from app.daily.models import DailyChange, DailyDecision
from app.daily.priority import (
    PrioritizedItem,
    PriorityItemType,
    PriorityReason,
    PriorityReasonCode,
)


class FakeStructuredLLM:
    """Deterministic structured LLM for generation tests."""

    def __init__(
        self,
        brief: DailyBrief,
    ) -> None:
        self.brief = brief
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
            self.brief,
            LLMResponse(
                content="{}",
                model="test-model",
                usage=None,
                latency_ms=12.5,
                finish_reason="stop",
            ),
        )


def _context(
    *,
    prioritized_items=(),
    decisions=(),
    changes=(),
    projects=(),
    people=(),
    risks=(),
) -> DailyIntelligenceContext:
    return DailyIntelligenceContext(
        day=datetime(2026, 10, 2).date(),
        timezone_name="Asia/Kolkata",
        window_start_utc=datetime(2026, 10, 1, 18, 30),
        window_end_utc=datetime(2026, 10, 2, 18, 30),
        prioritized_items=prioritized_items,
        recent_decisions=decisions,
        recent_changes=changes,
        recent_projects=projects,
        recent_people=people,
        recent_risks=risks,
    )


def _priority_item() -> PrioritizedItem:
    return PrioritizedItem(
        item_type=PriorityItemType.TASK,
        item_id=uuid4(),
        title="Review deployment",
        score=65,
        reasons=(
            PriorityReason(
                code=PriorityReasonCode.EXPLICIT_PRIORITY,
                points=35,
                message="Explicit priority: high.",
            ),
            PriorityReason(
                code=PriorityReasonCode.DUE_SOON,
                points=30,
                message="Due during the earlier part of the daily window.",
            ),
        ),
    )


@pytest.mark.asyncio
async def test_generation_returns_deterministic_empty_result() -> None:
    llm = FakeStructuredLLM(
        DailyBrief(
            summary="Should not be used.",
        )
    )

    service = DailyGenerationService(
        structured_llm=llm,
    )

    result = await service.generate(
        _context(),
    )

    assert result.brief.summary == (
        "No actionable items or recent intelligence "
        "were found for this day."
    )
    assert result.model is None
    assert result.latency_ms is None
    assert llm.messages == []


@pytest.mark.asyncio
async def test_generation_builds_structured_prompt() -> None:
    project_id = uuid4()
    person_id = uuid4()
    risk_id = uuid4()

    context = _context(
        prioritized_items=(
            _priority_item(),
        ),
        decisions=(
            DailyDecision(
                id=uuid4(),
                title="Database choice",
                description="Use PostgreSQL.",
                decision_date=datetime(2026, 10, 2, 9, 0),
                status="active",
                project_id=None,
            ),
        ),
        changes=(
            DailyChange(
                entity_type="project",
                entity_id=project_id,
                changed_at=datetime(2026, 10, 2, 10, 0),
            ),
        ),
        projects=(
            DailyProjectContext(
                id=project_id,
                name="PAIS",
                description="Personal intelligence system.",
                status="active",
                changed_at=datetime(2026, 10, 2, 10, 0),
            ),
        ),
        people=(
            DailyPersonContext(
                id=person_id,
                name="Alice",
                email="alice@example.com",
                changed_at=datetime(2026, 10, 2, 11, 0),
            ),
        ),
        risks=(
            DailyRiskContext(
                id=risk_id,
                title="Deployment risk",
                description="Deployment may be delayed.",
                severity="high",
                changed_at=datetime(2026, 10, 2, 12, 0),
            ),
        ),
    )

    llm = FakeStructuredLLM(
        DailyBrief(
            summary="Focus on deployment.",
            priorities=["Review deployment."],
            decisions=["Use PostgreSQL."],
            changes=["PAIS changed."],
            risks=["Deployment may be delayed."],
        )
    )

    service = DailyGenerationService(
        structured_llm=llm,
    )

    await service.generate(context)

    assert len(llm.messages) == 1

    messages = llm.messages[0]

    assert messages[0].role == "system"
    assert "daily intelligence" in (
        messages[0].content.lower()
    )

    assert messages[1].role == "user"

    prompt = messages[1].content

    assert "2026-10-02" in prompt
    assert "Asia/Kolkata" in prompt
    assert "Review deployment" in prompt
    assert "Database choice" in prompt
    assert "PAIS" in prompt
    assert "Alice" in prompt
    assert "Deployment risk" in prompt


@pytest.mark.asyncio
async def test_generation_passes_daily_brief_schema() -> None:
    llm = FakeStructuredLLM(
        DailyBrief(
            summary="Daily summary.",
        )
    )

    service = DailyGenerationService(
        structured_llm=llm,
    )

    await service.generate(
        _context(
            prioritized_items=(
                _priority_item(),
            ),
        ),
    )

    assert llm.schema is DailyBrief


@pytest.mark.asyncio
async def test_generation_passes_temperature() -> None:
    llm = FakeStructuredLLM(
        DailyBrief(
            summary="Daily summary.",
        )
    )

    service = DailyGenerationService(
        structured_llm=llm,
    )

    await service.generate(
        _context(
            prioritized_items=(
                _priority_item(),
            ),
        ),
        temperature=0.2,
    )

    assert llm.temperature == 0.2


@pytest.mark.asyncio
async def test_generation_returns_provider_metadata() -> None:
    llm = FakeStructuredLLM(
        DailyBrief(
            summary="Daily summary.",
        )
    )

    service = DailyGenerationService(
        structured_llm=llm,
    )

    result = await service.generate(
        _context(
            prioritized_items=(
                _priority_item(),
            ),
        ),
    )

    assert result.model == "test-model"
    assert result.latency_ms == 12.5


@pytest.mark.asyncio
async def test_generation_preserves_structured_llm_output() -> None:
    brief = DailyBrief(
        summary="Deployment requires attention.",
        priorities=[
            "Review deployment",
            "Complete testing",
        ],
        decisions=[
            "Use PostgreSQL",
        ],
        changes=[
            "PAIS project was updated",
        ],
        risks=[
            "Deployment may be delayed",
        ],
    )

    llm = FakeStructuredLLM(brief)

    service = DailyGenerationService(
        structured_llm=llm,
    )

    result = await service.generate(
        _context(
            prioritized_items=(
                _priority_item(),
            ),
        ),
    )

    assert result.brief == brief


@pytest.mark.asyncio
async def test_generation_does_not_call_llm_for_only_empty_context() -> None:
    llm = FakeStructuredLLM(
        DailyBrief(
            summary="Should not be generated.",
        )
    )

    service = DailyGenerationService(
        structured_llm=llm,
    )

    result = await service.generate(
        _context(),
    )

    assert llm.messages == []
    assert result.model is None


def test_daily_brief_requires_summary() -> None:
    with pytest.raises(ValueError):
        DailyBrief(summary="")


def test_daily_brief_allows_empty_sections() -> None:
    brief = DailyBrief(
        summary="Nothing requires immediate action.",
    )

    assert brief.priorities == []
    assert brief.decisions == []
    assert brief.changes == []
    assert brief.risks == []