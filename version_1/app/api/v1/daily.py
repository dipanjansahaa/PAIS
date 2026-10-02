"""Daily intelligence API endpoints."""

from __future__ import annotations

from datetime import date
# from functools import lru_cache
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Query
from app.llm.tracked import TrackedLLMProvider
from app.observability.models import ModelRunOperation
from pydantic import AfterValidator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.api.v1.schemas.daily import DailyResponse
from app.core.config import settings
from app.daily.generation import DailyGenerationService
from app.daily.workflow import DailyWorkflowService
from app.database.models.user import User
from app.database.session import get_db
from app.llm.factory import get_llm_provider
from app.llm.structured import StructuredLLMProvider


router = APIRouter(
    prefix="/daily",
    tags=["daily"],
)


def validate_timezone_name(value: str) -> str:
    """Validate that the supplied timezone is a valid IANA timezone."""

    value = value.strip()

    if not value:
        raise ValueError("Timezone name must not be empty.")

    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone: {value}") from exc

    return value


TimezoneName = Annotated[
    str,
    Query(min_length=1),
    AfterValidator(validate_timezone_name),
]


def get_daily_workflow_service(
    db_session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DailyWorkflowService:
    """Return the production daily intelligence workflow."""

    llm_provider = TrackedLLMProvider(
        provider=get_llm_provider(),
        user_id=current_user.id,
        operation=ModelRunOperation.DAILY_GENERATION,
        provider_name=settings.llm_provider,
        session=db_session,
    )

    structured_llm = StructuredLLMProvider(
        llm_provider,
    )

    generation_service = DailyGenerationService(
        structured_llm=structured_llm,
    )

    return DailyWorkflowService(
        generation_service=generation_service,
    )


@router.get(
    "",
    response_model=DailyResponse,
)
async def daily(
    day: date,
    timezone_name: TimezoneName,
    db_session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workflow: DailyWorkflowService = Depends(
        get_daily_workflow_service,
    ),
) -> DailyResponse:
    """Generate daily intelligence for the current user."""

    result = await workflow.run(
        db_session,
        user_id=current_user.id,
        day=day,
        timezone_name=timezone_name,
        temperature=settings.llm_temperature,
    )

    return DailyResponse(
        day=result.context.day,
        timezone_name=result.context.timezone_name,
        summary=result.generation.brief.summary,
        priorities=result.generation.brief.priorities,
        decisions=result.generation.brief.decisions,
        changes=result.generation.brief.changes,
        risks=result.generation.brief.risks,
        model=result.generation.model,
        latency_ms=result.generation.latency_ms,
    )