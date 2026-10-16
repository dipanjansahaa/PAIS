"""Integration tests for the structured intelligence API."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.database.models.commitment import (
    Commitment,
    CommitmentSource,
)
from app.database.models.decision import Decision, DecisionSource
from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.person import Person, PersonSource
from app.database.models.project import Project, ProjectSource
from app.database.models.risk import Risk, RiskSource
from app.database.models.task import Task, TaskSource
from app.database.models.user import User
from app.main import app


@pytest_asyncio.fixture
async def intelligence_api_client(
    db_session: AsyncSession,
):
    """Create an authenticated API client for intelligence tests."""

    test_user = User(
        email=f"intelligence-api-{uuid4()}@example.com",
        display_name="Intelligence API User",
    )

    other_user = User(
        email=f"intelligence-other-{uuid4()}@example.com",
        display_name="Other Intelligence User",
    )

    db_session.add_all(
        [
            test_user,
            other_user,
        ]
    )
    await db_session.flush()

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = (
        override_get_current_user
    )

    transport = ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield client, test_user, other_user

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_intelligence_endpoint_returns_user_intelligence(
    intelligence_api_client,
    db_session: AsyncSession,
) -> None:
    client, test_user, other_user = intelligence_api_client

    document = Document(
        user_id=test_user.id,
        title="Intelligence Source",
        source_type="test",
        file_name="intelligence.txt",
        mime_type="text/plain",
        content_hash=uuid4().hex,
        raw_text="Structured intelligence source.",
    )

    other_document = Document(
        user_id=other_user.id,
        title="Other User Source",
        source_type="test",
        file_name="other.txt",
        mime_type="text/plain",
        content_hash=uuid4().hex,
        raw_text="Private other user source.",
    )

    db_session.add_all(
        [
            document,
            other_document,
        ]
    )
    await db_session.flush()

    chunk = DocumentChunk(
        document_id=document.id,
        chunk_index=0,
        content="Structured intelligence source.",
        embedding=[1.0] + [0.0] * 383,
    )

    other_chunk = DocumentChunk(
        document_id=other_document.id,
        chunk_index=0,
        content="Private other user source.",
        embedding=[1.0] + [0.0] * 383,
    )

    db_session.add_all(
        [
            chunk,
            other_chunk,
        ]
    )
    await db_session.flush()

    project = Project(
        user_id=test_user.id,
        name="PAIS V1",
        description="PAIS project.",
        status="active",
    )

    other_project = Project(
        user_id=other_user.id,
        name="Other Project",
        description="Private project.",
        status="active",
    )

    db_session.add_all(
        [
            project,
            other_project,
        ]
    )
    await db_session.flush()

    task = Task(
        user_id=test_user.id,
        project_id=project.id,
        description="Review deployment",
        owner="Dipanjan",
        priority="high",
        status="open",
    )

    task_source = TaskSource(
        task=task,
        chunk_id=chunk.id,
    )

    commitment = Commitment(
        user_id=test_user.id,
        project_id=project.id,
        description="Complete deployment review",
        owner="Dipanjan",
        status="open",
    )

    commitment_source = CommitmentSource(
        commitment=commitment,
        chunk_id=chunk.id,
    )

    decision = Decision(
        user_id=test_user.id,
        project_id=project.id,
        title="Use PostgreSQL",
        description="Use PostgreSQL for PAIS persistence.",
        decision_date=datetime.now(timezone.utc),
        status="active",
    )

    decision_source = DecisionSource(
        decision=decision,
        chunk_id=chunk.id,
    )

    project_source = ProjectSource(
        project=project,
        chunk_id=chunk.id,
    )

    person = Person(
        user_id=test_user.id,
        name="Dipanjan",
        email="dipanjan@example.com",
    )

    person_source = PersonSource(
        person=person,
        chunk_id=chunk.id,
    )

    risk = Risk(
        user_id=test_user.id,
        title="Deployment risk",
        description="Deployment requires validation.",
        severity="medium",
    )

    risk_source = RiskSource(
        risk=risk,
        chunk_id=chunk.id,
    )

    other_task = Task(
        user_id=other_user.id,
        project_id=other_project.id,
        description="Private task",
        owner="Other User",
        priority="high",
        status="open",
    )

    other_task_source = TaskSource(
        task=other_task,
        chunk_id=other_chunk.id,
    )

    db_session.add_all(
        [
            task,
            task_source,
            commitment,
            commitment_source,
            decision,
            decision_source,
            project_source,
            person,
            person_source,
            risk,
            risk_source,
            other_task,
            other_task_source,
        ]
    )

    await db_session.flush()

    response = await client.get(
        "/api/v1/intelligence",
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data["tasks"]) == 1
    assert len(data["commitments"]) == 1
    assert len(data["decisions"]) == 1
    assert len(data["projects"]) == 1
    assert len(data["people"]) == 1
    assert len(data["risks"]) == 1

    assert data["tasks"][0]["description"] == (
        "Review deployment"
    )

    assert data["tasks"][0]["source_chunk_ids"] == [
        str(chunk.id)
    ]

    assert data["commitments"][0]["description"] == (
        "Complete deployment review"
    )

    assert data["commitments"][0]["source_chunk_ids"] == [
        str(chunk.id)
    ]

    assert data["decisions"][0]["title"] == "Use PostgreSQL"
    assert data["decisions"][0]["source_chunk_ids"] == [
        str(chunk.id)
    ]

    assert data["projects"][0]["name"] == "PAIS V1"
    assert data["projects"][0]["source_chunk_ids"] == [
        str(chunk.id)
    ]

    assert data["people"][0]["name"] == "Dipanjan"
    assert data["people"][0]["source_chunk_ids"] == [
        str(chunk.id)
    ]

    assert data["risks"][0]["title"] == "Deployment risk"
    assert data["risks"][0]["source_chunk_ids"] == [
        str(chunk.id)
    ]

    assert all(
        task_item["description"] != "Private task"
        for task_item in data["tasks"]
    )


@pytest.mark.asyncio
async def test_intelligence_endpoint_returns_empty_collections_for_new_user(
    intelligence_api_client,
) -> None:
    client, _, _ = intelligence_api_client

    response = await client.get(
        "/api/v1/intelligence",
    )

    assert response.status_code == 200

    assert response.json() == {
        "tasks": [],
        "commitments": [],
        "decisions": [],
        "projects": [],
        "people": [],
        "risks": [],
    }