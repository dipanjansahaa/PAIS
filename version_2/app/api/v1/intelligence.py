"""Structured intelligence API endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.api.v1.schemas.intelligence import (
    CommitmentResponse,
    DecisionResponse,
    IntelligenceResponse,
    PersonResponse,
    ProjectResponse,
    RiskResponse,
    TaskResponse,
)
from app.database.models.user import User
from app.database.session import get_db
from app.intelligence.read_service import IntelligenceReadService


router = APIRouter(
    prefix="/intelligence",
    tags=["intelligence"],
)


def get_intelligence_read_service() -> IntelligenceReadService:
    """Return the structured intelligence read service."""

    return IntelligenceReadService()


@router.get(
    "",
    response_model=IntelligenceResponse,
)
async def get_intelligence(
    db_session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    read_service: Annotated[
        IntelligenceReadService,
        Depends(get_intelligence_read_service),
    ],
) -> IntelligenceResponse:
    """Return structured intelligence for the authenticated user."""

    snapshot = await read_service.get_snapshot(
        db_session,
        user_id=current_user.id,
    )

    return IntelligenceResponse(
        tasks=[
            TaskResponse(
                id=task.id,
                project_id=task.project_id,
                commitment_id=task.commitment_id,
                description=task.description,
                owner=task.owner,
                due_at=task.due_at,
                priority=task.priority,
                status=task.status,
                source_chunk_ids=[
                    source.chunk_id
                    for source in task.sources
                ],
            )
            for task in snapshot.tasks
        ],
        commitments=[
            CommitmentResponse(
                id=commitment.id,
                project_id=commitment.project_id,
                description=commitment.description,
                owner=commitment.owner,
                deadline_at=commitment.deadline_at,
                status=commitment.status,
                source_chunk_ids=[
                    source.chunk_id
                    for source in commitment.sources
                ],
            )
            for commitment in snapshot.commitments
        ],
        decisions=[
            DecisionResponse(
                id=decision.id,
                project_id=decision.project_id,
                title=decision.title,
                description=decision.description,
                decision_date=decision.decision_date,
                status=decision.status,
                source_chunk_ids=[
                    source.chunk_id
                    for source in decision.sources
                ],
            )
            for decision in snapshot.decisions
        ],
        projects=[
            ProjectResponse(
                id=project.id,
                name=project.name,
                description=project.description,
                status=project.status,
                source_chunk_ids=[
                    source.chunk_id
                    for source in project.sources
                ],
            )
            for project in snapshot.projects
        ],
        people=[
            PersonResponse(
                id=person.id,
                name=person.name,
                email=person.email,
                source_chunk_ids=[
                    source.chunk_id
                    for source in person.sources
                ],
            )
            for person in snapshot.people
        ],
        risks=[
            RiskResponse(
                id=risk.id,
                title=risk.title,
                description=risk.description,
                severity=risk.severity,
                source_chunk_ids=[
                    source.chunk_id
                    for source in risk.sources
                ],
            )
            for risk in snapshot.risks
        ],
    )