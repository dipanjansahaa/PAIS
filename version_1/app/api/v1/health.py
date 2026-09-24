"""Liveness and readiness endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Liveness response."""

    status: str


class ReadinessResponse(BaseModel):
    """Readiness response."""

    status: str
    database: str


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness check",
)
async def health() -> HealthResponse:
    """Confirm that the API process is alive.

    This endpoint intentionally does not depend on external services.
    """

    return HealthResponse(status="ok")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ReadinessResponse,
            "description": "The application is not ready to serve traffic.",
        }
    },
    summary="Readiness check",
)
async def ready(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReadinessResponse:
    """Confirm that required infrastructure is reachable."""

    try:
        await db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(status="not_ready", database="unavailable")

    return ReadinessResponse(status="ready", database="ok")
