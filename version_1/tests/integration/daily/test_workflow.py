"""Integration tests for the end-to-end daily intelligence workflow."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.daily.generation import DailyBrief, DailyGenerationService
from app.daily.workflow import DailyWorkflowService
from app.database.models.person import Person
from app.database.models.project import Project
from app.database.models.risk import Risk
from app.database.models.task import Task
from app.database.models.user import User
from app.llm.models import LLMResponse


class FakeStructuredLLM:
    """Deterministic structured LLM for workflow integration tests."""

    def __init__(
        self,
        brief: DailyBrief,
    ) -> None:
        self.brief = brief
        self.messages = []
        self.schema = None
        self.temperature = None
        self.call_count = 0

    async def generate(
        self,
        messages,
        *,
        schema,
        temperature=0.0,
    ):
        self.call_count += 1
        self.messages.append(messages)
        self.schema = schema
        self.temperature = temperature

        return (
            self.brief,
            LLMResponse(
                content="{}",
                model="workflow-test-model",
                usage=None,
                latency_ms=15.0,
                finish_reason="stop",
            ),
        )


def _recent_timestamp() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_daily_workflow_runs_end_to_end(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"daily-workflow-{uuid4()}@example.com",
        display_name="Workflow User",
    )

    db_session.add(user)
    await db_session.flush()

    recent_at = _recent_timestamp()

    project = Project(
        user_id=user.id,
        name="PAIS",
        description="Personal intelligence system.",
        status="active",
        updated_at=recent_at,
    )

    person = Person(
        user_id=user.id,
        name="Alice",
        email="alice@example.com",
        updated_at=recent_at,
    )

    risk = Risk(
        user_id=user.id,
        title="Deployment risk",
        description="Deployment may be delayed.",
        severity="high",
        updated_at=recent_at,
    )

    db_session.add_all(
        [
            project,
            person,
            risk,
        ]
    )

    await db_session.flush()

    task = Task(
        user_id=user.id,
        description="Review deployment",
        status="open",
        priority="high",
        project_id=project.id,
        due_at=recent_at,
        updated_at=recent_at,
    )

    db_session.add(task)
    await db_session.flush()

    llm = FakeStructuredLLM(
        DailyBrief(
            summary="Deployment requires attention.",
            priorities=["Review deployment."],
            changes=["PAIS was updated."],
            risks=["Deployment may be delayed."],
        )
    )

    generation_service = DailyGenerationService(
        structured_llm=llm,
    )

    workflow = DailyWorkflowService(
        generation_service=generation_service,
    )

    result = await workflow.run(
        db_session,
        user_id=user.id,
        day=datetime.now(timezone.utc).date(),
        timezone_name="UTC",
    )

    assert result.snapshot.open_tasks
    assert result.snapshot.open_tasks[0].id == task.id

    assert result.context.prioritized_items
    assert result.context.prioritized_items[0].item_id == task.id

    assert result.context.recent_projects
    assert result.context.recent_projects[0].id == project.id

    assert result.context.recent_people
    assert result.context.recent_people[0].id == person.id

    assert result.context.recent_risks
    assert result.context.recent_risks[0].id == risk.id

    assert result.generation.brief.summary == (
        "Deployment requires attention."
    )

    assert result.generation.model == "workflow-test-model"
    assert result.generation.latency_ms == 15.0

    assert llm.call_count == 1
    assert llm.schema is DailyBrief

    prompt = llm.messages[0][1].content

    assert "Review deployment" in prompt
    assert "PAIS" in prompt
    assert "Alice" in prompt
    assert "Deployment risk" in prompt


@pytest.mark.integration
@pytest.mark.asyncio
async def test_daily_workflow_preserves_user_isolation(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"daily-workflow-owner-{uuid4()}@example.com",
        display_name="Workflow Owner",
    )

    other_user = User(
        email=f"daily-workflow-other-{uuid4()}@example.com",
        display_name="Other Workflow User",
    )

    db_session.add_all([user, other_user])
    await db_session.flush()

    recent_at = _recent_timestamp()

    own_project = Project(
        user_id=user.id,
        name="Own Project",
        updated_at=recent_at,
    )

    foreign_project = Project(
        user_id=other_user.id,
        name="Foreign Project",
        updated_at=recent_at,
    )

    own_person = Person(
        user_id=user.id,
        name="Own Person",
        updated_at=recent_at,
    )

    foreign_person = Person(
        user_id=other_user.id,
        name="Foreign Person",
        updated_at=recent_at,
    )

    own_risk = Risk(
        user_id=user.id,
        title="Own Risk",
        updated_at=recent_at,
    )

    foreign_risk = Risk(
        user_id=other_user.id,
        title="Foreign Risk",
        updated_at=recent_at,
    )

    db_session.add_all(
        [
            own_project,
            foreign_project,
            own_person,
            foreign_person,
            own_risk,
            foreign_risk,
        ]
    )
    await db_session.flush()

    llm = FakeStructuredLLM(
        DailyBrief(
            summary="Daily intelligence.",
        )
    )

    workflow = DailyWorkflowService(
        generation_service=DailyGenerationService(
            structured_llm=llm,
        ),
    )

    result = await workflow.run(
        db_session,
        user_id=user.id,
        day=datetime.now(timezone.utc).date(),
        timezone_name="UTC",
    )

    assert [project.id for project in result.context.recent_projects] == [
        own_project.id,
    ]

    assert [person.id for person in result.context.recent_people] == [
        own_person.id,
    ]

    assert [risk.id for risk in result.context.recent_risks] == [
        own_risk.id,
    ]

    prompt = llm.messages[0][1].content

    assert "Own Project" in prompt
    assert "Own Person" in prompt
    assert "Own Risk" in prompt

    assert "Foreign Project" not in prompt
    assert "Foreign Person" not in prompt
    assert "Foreign Risk" not in prompt


@pytest.mark.integration
@pytest.mark.asyncio
async def test_daily_workflow_skips_llm_for_empty_day(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"daily-workflow-empty-{uuid4()}@example.com",
        display_name="Empty Workflow User",
    )

    db_session.add(user)
    await db_session.flush()

    llm = FakeStructuredLLM(
        DailyBrief(
            summary="Should not be generated.",
        )
    )

    workflow = DailyWorkflowService(
        generation_service=DailyGenerationService(
            structured_llm=llm,
        ),
    )

    result = await workflow.run(
        db_session,
        user_id=user.id,
        day=datetime.now(timezone.utc).date(),
        timezone_name="UTC",
    )

    assert result.snapshot.open_tasks == ()
    assert result.snapshot.open_commitments == ()
    assert result.snapshot.recent_decisions == ()
    assert result.snapshot.recent_changes == ()

    assert result.context.prioritized_items == ()
    assert result.context.recent_projects == ()
    assert result.context.recent_people == ()
    assert result.context.recent_risks == ()

    assert result.generation.model is None
    assert result.generation.latency_ms is None
    assert llm.call_count == 0