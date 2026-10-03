from __future__ import annotations

import json
from datetime import date, datetime, timezone
from io import BytesIO

import pytest
from sqlalchemy import select

from app.api.v1.daily import get_daily_workflow_service
from app.api.v1.search import get_search_service
from app.commitments.service import CommitmentService
from app.decisions.service import DecisionService
from app.database.models.commitment import Commitment
from app.database.models.decision import Decision
from app.database.models.person import Person
from app.database.models.project import Project
from app.database.models.risk import Risk
from app.database.models.task import Task
from app.database.models.document_chunk import DocumentChunk
from app.daily.generation import DailyBrief, DailyGenerationService
from app.daily.workflow import DailyWorkflowService
from app.intelligence.models import (
    CommitmentCandidate,
    DecisionCandidate,
    IntelligenceSource,
    PersonCandidate,
    ProjectCandidate,
    RiskCandidate,
    StructuredIntelligence,
    TaskCandidate,
)
from app.intelligence.service import IntelligenceExtractionService
from app.llm.models import LLMResponse, Message
from app.llm.structured import StructuredLLMProvider
from app.main import app
from app.people.service import PersonService
from app.projects.service import ProjectService
from app.risks.service import RiskService
from app.tasks.service import TaskService


E2E_DAY = date(2026, 10, 3)

E2E_DAY_START_UTC = datetime(
    2026,
    10,
    2,
    18,
    30,
)

E2E_DAY_MIDPOINT_UTC = datetime(
    2026,
    10,
    3,
    6,
    30,
)

E2E_TASK_DUE_AT = datetime(
    2026,
    10,
    3,
    2,
    0,
)

E2E_COMMITMENT_DEADLINE = datetime(
    2026,
    10,
    3,
    10,
)


class FakeStructuredExtractionLLM:
    """Deterministic structured LLM for intelligence extraction."""

    def __init__(
        self,
        *,
        chunk_id,
    ) -> None:
        self.chunk_id = chunk_id
        self.messages: list[list[Message]] = []

    async def generate(
        self,
        messages,
        *,
        schema,
        temperature=0.0,
    ):
        self.messages.append(messages)

        assert schema is StructuredIntelligence

        intelligence = StructuredIntelligence(
            tasks=[
                TaskCandidate(
                    description="Complete the API deployment review",
                    owner="Dipanjan",
                    due_at=E2E_TASK_DUE_AT,
                    priority="high",
                    sources=[
                        IntelligenceSource(
                            chunk_id=self.chunk_id,
                        )
                    ],
                )
            ],
            commitments=[
                CommitmentCandidate(
                    description="Deliver the deployment plan",
                    owner="Dipanjan",
                    deadline_at=E2E_COMMITMENT_DEADLINE,
                    sources=[
                        IntelligenceSource(
                            chunk_id=self.chunk_id,
                        )
                    ],
                )
            ],
            decisions=[
                DecisionCandidate(
                    title="Use PostgreSQL for PAIS",
                    description=(
                        "PAIS will use PostgreSQL with pgvector."
                    ),
                    decision_date=E2E_TASK_DUE_AT,
                    sources=[
                        IntelligenceSource(
                            chunk_id=self.chunk_id,
                        )
                    ],
                )
            ],
            projects=[
                ProjectCandidate(
                    name="PAIS Productionization",
                    description=(
                        "Prepare PAIS for real personal daily use."
                    ),
                    sources=[
                        IntelligenceSource(
                            chunk_id=self.chunk_id,
                        )
                    ],
                )
            ],
            people=[
                PersonCandidate(
                    name="Alice",
                    email="alice@example.com",
                    sources=[
                        IntelligenceSource(
                            chunk_id=self.chunk_id,
                        )
                    ],
                )
            ],
            risks=[
                RiskCandidate(
                    title="Deployment risk",
                    description=(
                        "The deployment plan still needs review."
                    ),
                    severity="medium",
                    sources=[
                        IntelligenceSource(
                            chunk_id=self.chunk_id,
                        )
                    ],
                )
            ],
        )

        return (
            intelligence,
            LLMResponse(
                content="{}",
                model="e2e-extraction-model",
                usage=None,
                latency_ms=2.0,
                finish_reason="stop",
            ),
        )


class FakeDailyLLM:
    """Deterministic LLM for daily intelligence generation."""

    def __init__(self) -> None:
        self.messages: list[list[Message]] = []

    async def generate(
        self,
        messages,
        *,
        temperature=0.0,
        response_schema=None,
    ) -> LLMResponse:
        self.messages.append(messages)

        assert response_schema is DailyBrief

        prompt = messages[-1].content

        assert "Complete the API deployment review" in prompt
        assert "Deliver the deployment plan" in prompt
        assert "Use PostgreSQL for PAIS" in prompt
        assert "PAIS Productionization" in prompt
        assert "Alice" in prompt
        assert "Deployment risk" in prompt

        payload = {
            "summary": (
                "PAIS has an active deployment review, "
                "a delivery commitment, and a deployment risk."
            ),
            "priorities": [
                "Complete the API deployment review",
                "Deliver the deployment plan",
            ],
            "decisions": [
                "Use PostgreSQL for PAIS",
            ],
            "changes": [
                "PAIS Productionization was updated.",
                "Alice is associated with the current intelligence.",
            ],
            "risks": [
                "Deployment risk",
            ],
        }

        return LLMResponse(
            content=json.dumps(payload),
            model="e2e-daily-model",
            usage=None,
            latency_ms=3.0,
            finish_reason="stop",
        )


@pytest.mark.asyncio
async def test_structured_intelligence_flows_into_daily_end_to_end(
    e2e_api_client,
    db_session,
):
    """
    Verify the complete structured-intelligence-to-daily workflow.

    The workflow starts with a real document upload, performs real
    retrieval, runs structured intelligence extraction, persists the
    extracted domain objects, and finally calls the real Daily API.
    """

    client, test_user = e2e_api_client

    content = (
        b"# PAIS Weekly Planning\n\n"
        b"The API deployment review must be completed today.\n\n"
        b"Dipanjan will deliver the deployment plan today.\n\n"
        b"The team decided to use PostgreSQL with pgvector for PAIS.\n\n"
        b"PAIS Productionization is the project for preparing PAIS "
        b"for real personal daily use.\n\n"
        b"Alice is helping with the deployment review.\n\n"
        b"The deployment plan still has a medium deployment risk."
    )

    upload_response = await client.post(
        "/api/v1/documents",
        files={
            "file": (
                "pais-weekly-planning.md",
                BytesIO(content),
                "text/markdown",
            )
        },
        data={
            "title": "PAIS Weekly Planning",
            "source_type": "markdown",
        },
    )

    assert upload_response.status_code == 201

    uploaded_document = upload_response.json()
    document_id = uploaded_document["id"]

    chunks = list(
        (
            await db_session.scalars(
                select(DocumentChunk).where(
                    DocumentChunk.document_id == document_id
                )
            )
        ).all()
    )

    assert chunks

    search_service = app.dependency_overrides[
        get_search_service
    ]()

    retrieval_results = await search_service.search(
        db_session,
        user_id=test_user.id,
        query=(
            "API deployment review deployment plan "
            "PostgreSQL pgvector"
        ),
        top_k=5,
    )

    assert retrieval_results

    retrieved_chunk = next(
        result
        for result in retrieval_results
        if result.chunk_id in {chunk.id for chunk in chunks}
    )

    extraction_llm = FakeStructuredExtractionLLM(
        chunk_id=retrieved_chunk.chunk_id,
    )

    extraction_service = IntelligenceExtractionService(
        structured_llm=extraction_llm,
    )

    extraction_result = await extraction_service.extract(
        retrieval_results,
    )

    intelligence = extraction_result.intelligence

    assert len(intelligence.tasks) == 1
    assert len(intelligence.commitments) == 1
    assert len(intelligence.decisions) == 1
    assert len(intelligence.projects) == 1
    assert len(intelligence.people) == 1
    assert len(intelligence.risks) == 1

    source_chunk_ids = {
        retrieved_chunk.chunk_id,
    }

    for collection in (
        intelligence.tasks,
        intelligence.commitments,
        intelligence.decisions,
        intelligence.projects,
        intelligence.people,
        intelligence.risks,
    ):
        assert collection
        assert all(
            source.chunk_id in source_chunk_ids
            for item in collection
            for source in item.sources
        )

    project = await ProjectService().create_from_candidate(
        db_session,
        user_id=test_user.id,
        candidate=intelligence.projects[0],
    )

    person = await PersonService().create_from_candidate(
        db_session,
        user_id=test_user.id,
        candidate=intelligence.people[0],
    )

    risk = await RiskService().create_from_candidate(
        db_session,
        user_id=test_user.id,
        candidate=intelligence.risks[0],
    )

    commitment = await CommitmentService().create_from_candidate(
        db_session,
        user_id=test_user.id,
        candidate=intelligence.commitments[0],
        project_id=project.id,
    )

    task = await TaskService().create_from_candidate(
        db_session,
        user_id=test_user.id,
        candidate=intelligence.tasks[0],
        project_id=project.id,
        commitment_id=commitment.id,
    )

    decision = await DecisionService().create_from_candidate(
        db_session,
        user_id=test_user.id,
        candidate=intelligence.decisions[0],
        project_id=project.id,
    )

    task.updated_at = E2E_DAY_START_UTC
    commitment.updated_at = E2E_DAY_START_UTC
    decision.updated_at = E2E_DAY_START_UTC
    project.updated_at = E2E_DAY_START_UTC
    person.updated_at = E2E_DAY_START_UTC
    risk.updated_at = E2E_DAY_START_UTC

    await db_session.flush()

    persisted_task = await db_session.get(
        Task,
        task.id,
    )

    persisted_commitment = await db_session.get(
        Commitment,
        commitment.id,
    )

    persisted_decision = await db_session.get(
        Decision,
        decision.id,
    )

    persisted_project = await db_session.get(
        Project,
        project.id,
    )

    persisted_person = await db_session.get(
        Person,
        person.id,
    )

    persisted_risk = await db_session.get(
        Risk,
        risk.id,
    )

    assert persisted_task is not None
    assert persisted_commitment is not None
    assert persisted_decision is not None
    assert persisted_project is not None
    assert persisted_person is not None
    assert persisted_risk is not None

    assert persisted_task.status == "open"
    assert persisted_commitment.status == "open"
    assert persisted_decision.status == "active"

    daily_llm = FakeDailyLLM()

    daily_generation_service = DailyGenerationService(
        structured_llm=StructuredLLMProvider(
            daily_llm,
        ),
    )

    daily_workflow = DailyWorkflowService(
        generation_service=daily_generation_service,
    )

    def override_get_daily_workflow_service():
        return daily_workflow

    app.dependency_overrides[
        get_daily_workflow_service
    ] = override_get_daily_workflow_service

    try:
        daily_response = await client.get(
            "/api/v1/daily",
            params={
                "day": E2E_DAY.isoformat(),
                "timezone_name": "Asia/Kolkata",
            },
        )

        assert daily_response.status_code == 200

        data = daily_response.json()

        assert data["day"] == E2E_DAY.isoformat()
        assert data["timezone_name"] == "Asia/Kolkata"

        assert data["summary"] == (
            "PAIS has an active deployment review, "
            "a delivery commitment, and a deployment risk."
        )

        assert data["priorities"] == [
            "Complete the API deployment review",
            "Deliver the deployment plan",
        ]

        assert data["decisions"] == [
            "Use PostgreSQL for PAIS",
        ]

        assert data["changes"] == [
            "PAIS Productionization was updated.",
            "Alice is associated with the current intelligence.",
        ]

        assert data["risks"] == [
            "Deployment risk",
        ]

        assert data["model"] == "e2e-daily-model"
        assert data["latency_ms"] == 3.0

        assert len(daily_llm.messages) == 1

        generation_prompt = daily_llm.messages[0][-1].content

        assert "PRIORITIZED ITEMS:" in generation_prompt
        assert "RECENT DECISIONS:" in generation_prompt
        assert "RECENT CHANGES:" in generation_prompt
        assert "RECENT PROJECTS:" in generation_prompt
        assert "RECENT PEOPLE:" in generation_prompt
        assert "RECENT RISKS:" in generation_prompt

        assert "Complete the API deployment review" in generation_prompt
        assert "Deliver the deployment plan" in generation_prompt
        assert "Use PostgreSQL for PAIS" in generation_prompt
        assert "PAIS Productionization" in generation_prompt
        assert "Alice" in generation_prompt
        assert "Deployment risk" in generation_prompt

    finally:
        app.dependency_overrides.pop(
            get_daily_workflow_service,
            None,
        )