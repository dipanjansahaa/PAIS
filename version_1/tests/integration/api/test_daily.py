"""Integration tests for the daily intelligence API."""

from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.api.v1.daily import get_daily_workflow_service
from app.daily.generation import DailyBrief, DailyGenerationResult
from app.daily.models import DailySnapshot
from app.daily.workflow import DailyWorkflowResult
from app.database.models.user import User
from app.main import app


class FakeDailyWorkflow:
    """Deterministic workflow used by API integration tests."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def run(
        self,
        session,
        *,
        user_id,
        day,
        timezone_name,
        temperature,
    ) -> DailyWorkflowResult:
        self.calls.append(
            {
                "user_id": user_id,
                "day": day,
                "timezone_name": timezone_name,
                "temperature": temperature,
            }
        )

        snapshot = DailySnapshot(
            day=day,
            timezone_name=timezone_name,
            window_start_utc=datetime(
                2026, 10, 1, 18, 30
            ),
            window_end_utc=datetime(
                2026, 10, 1, 18, 30
            ),
            open_tasks=(),
            open_commitments=(),
            recent_decisions=(),
            recent_changes=(),
        )

        from app.daily.context import DailyIntelligenceContext

        context = DailyIntelligenceContext(
            day=day,
            timezone_name=timezone_name,
            window_start_utc=snapshot.window_start_utc,
            window_end_utc=snapshot.window_end_utc,
            prioritized_items=(),
            recent_decisions=(),
            recent_changes=(),
        )

        generation = DailyGenerationResult(
            brief=DailyBrief(
                summary="Focus on deployment.",
                priorities=["Review deployment."],
                decisions=["Use PostgreSQL."],
                changes=["PAIS project updated."],
                risks=["Deployment risk remains."],
            ),
            model="test-model",
            latency_ms=12.5,
        )

        return DailyWorkflowResult(
            snapshot=snapshot,
            context=context,
            generation=generation,
        )


@pytest_asyncio.fixture
async def daily_api_client(
    db_session: AsyncSession,
):
    """Create an isolated API client for Daily Intelligence."""

    test_user = User(
        email=f"daily-api-{uuid4()}@example.com",
        display_name="Daily API User",
    )

    db_session.add(test_user)
    await db_session.flush()

    fake_workflow = FakeDailyWorkflow()

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = (
        override_get_current_user
    )
    app.dependency_overrides[get_daily_workflow_service] = (
        lambda: fake_workflow
    )

    transport = ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield client, test_user, fake_workflow

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_daily_endpoint_returns_daily_intelligence(
    daily_api_client,
) -> None:
    client, test_user, workflow = daily_api_client

    response = await client.get(
        "/api/v1/daily",
        params={
            "day": "2026-10-02",
            "timezone_name": "Asia/Kolkata",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data == {
        "day": "2026-10-02",
        "timezone_name": "Asia/Kolkata",
        "summary": "Focus on deployment.",
        "priorities": ["Review deployment."],
        "decisions": ["Use PostgreSQL."],
        "changes": ["PAIS project updated."],
        "risks": ["Deployment risk remains."],
        "model": "test-model",
        "latency_ms": 12.5,
    }

    assert len(workflow.calls) == 1
    assert workflow.calls[0]["user_id"] == test_user.id
    assert workflow.calls[0]["day"] == date(2026, 10, 2)
    assert workflow.calls[0]["timezone_name"] == "Asia/Kolkata"


@pytest.mark.asyncio
async def test_daily_endpoint_rejects_invalid_timezone(
    daily_api_client,
) -> None:
    client, _, workflow = daily_api_client

    response = await client.get(
        "/api/v1/daily",
        params={
            "day": "2026-10-02",
            "timezone_name": "Not/A/Timezone",
        },
    )

    assert response.status_code == 422
    assert workflow.calls == []


@pytest.mark.asyncio
async def test_daily_endpoint_requires_day(
    daily_api_client,
) -> None:
    client, _, workflow = daily_api_client

    response = await client.get(
        "/api/v1/daily",
        params={
            "timezone_name": "Asia/Kolkata",
        },
    )

    assert response.status_code == 422
    assert workflow.calls == []


@pytest.mark.asyncio
async def test_daily_endpoint_requires_timezone(
    daily_api_client,
) -> None:
    client, _, workflow = daily_api_client

    response = await client.get(
        "/api/v1/daily",
        params={
            "day": "2026-10-02",
        },
    )

    assert response.status_code == 422
    assert workflow.calls == []