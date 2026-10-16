
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

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
from app.intelligence.persistence_service import (
    IntelligencePersistenceService,
)


@pytest.mark.asyncio
async def test_persist_routes_all_six_supported_categories():
    project_service = AsyncMock()
    person_service = AsyncMock()
    risk_service = AsyncMock()
    commitment_service = AsyncMock()
    task_service = AsyncMock()
    decision_service = AsyncMock()
    session = AsyncMock()

    service = IntelligencePersistenceService(
        project_service=project_service,
        person_service=person_service,
        risk_service=risk_service,
        commitment_service=commitment_service,
        task_service=task_service,
        decision_service=decision_service,
    )

    user_id = uuid4()
    source = [IntelligenceSource(chunk_id=uuid4())]

    intelligence = StructuredIntelligence(
        projects=[
            ProjectCandidate(name="PAIS", sources=source),
        ],
        people=[
            PersonCandidate(name="Alice", sources=source),
        ],
        risks=[
            RiskCandidate(title="Deployment risk", sources=source),
        ],
        commitments=[
            CommitmentCandidate(
                description="Deliver the plan",
                sources=source,
            ),
        ],
        tasks=[
            TaskCandidate(
                description="Review the API",
                sources=source,
            ),
        ],
        decisions=[
            DecisionCandidate(
                title="Use PostgreSQL",
                description="Use PostgreSQL for PAIS.",
                sources=source,
            ),
        ],
    )

    result = await service.persist(
        session,
        user_id=user_id,
        intelligence=intelligence,
    )

    assert result.projects == 1
    assert result.people == 1
    assert result.risks == 1
    assert result.commitments == 1
    assert result.tasks == 1
    assert result.decisions == 1

    project_service.create_from_candidate.assert_awaited_once()
    person_service.create_from_candidate.assert_awaited_once()
    risk_service.create_from_candidate.assert_awaited_once()
    commitment_service.create_from_candidate.assert_awaited_once()
    task_service.create_from_candidate.assert_awaited_once()
    decision_service.create_from_candidate.assert_awaited_once()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_persist_empty_intelligence_does_not_create_entities():
    session = AsyncMock()
    service = IntelligencePersistenceService(
        project_service=AsyncMock(),
        person_service=AsyncMock(),
        risk_service=AsyncMock(),
        commitment_service=AsyncMock(),
        task_service=AsyncMock(),
        decision_service=AsyncMock(),
    )

    result = await service.persist(
        session,
        user_id=uuid4(),
        intelligence=StructuredIntelligence(),
    )

    assert result.projects == 0
    assert result.people == 0
    assert result.risks == 0
    assert result.commitments == 0
    assert result.tasks == 0
    assert result.decisions == 0
    assert result.unsupported_follow_ups == 0
    assert result.unsupported_deadlines == 0
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_persist_reports_categories_without_storage_models():
    service = IntelligencePersistenceService(
        project_service=AsyncMock(),
        person_service=AsyncMock(),
        risk_service=AsyncMock(),
        commitment_service=AsyncMock(),
        task_service=AsyncMock(),
        decision_service=AsyncMock(),
    )

    from app.intelligence.models import (
        DeadlineCandidate,
        FollowUpCandidate,
    )

    result = await service.persist(
        AsyncMock(),
        user_id=uuid4(),
        intelligence=StructuredIntelligence(
            follow_ups=[
                FollowUpCandidate(
                    description="Follow up with Alice",
                    sources=[
                        IntelligenceSource(chunk_id=uuid4()),
                    ],
                ),
            ],
            deadlines=[
                DeadlineCandidate(
                    description="Submit the report",
                    due_at="2026-10-20T12:00:00",
                    sources=[
                        IntelligenceSource(chunk_id=uuid4()),
                    ],
                ),
            ],
        ),
    )

    assert result.unsupported_follow_ups == 1
    assert result.unsupported_deadlines == 1
