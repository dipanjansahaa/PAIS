"""Schemas for the structured intelligence API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TaskResponse(BaseModel):
    """Structured task returned by the API."""

    id: UUID
    project_id: UUID | None
    commitment_id: UUID | None
    description: str
    owner: str | None
    due_at: datetime | None
    priority: str | None
    status: str
    source_chunk_ids: list[UUID]


class CommitmentResponse(BaseModel):
    """Structured commitment returned by the API."""

    id: UUID
    project_id: UUID | None
    description: str
    owner: str | None
    deadline_at: datetime | None
    status: str
    source_chunk_ids: list[UUID]


class DecisionResponse(BaseModel):
    """Structured decision returned by the API."""

    id: UUID
    project_id: UUID | None
    title: str
    description: str
    decision_date: datetime | None
    status: str
    source_chunk_ids: list[UUID]


class ProjectResponse(BaseModel):
    """Structured project returned by the API."""

    id: UUID
    name: str
    description: str | None
    status: str
    source_chunk_ids: list[UUID]


class PersonResponse(BaseModel):
    """Structured person returned by the API."""

    id: UUID
    name: str
    email: str | None
    source_chunk_ids: list[UUID]


class RiskResponse(BaseModel):
    """Structured risk returned by the API."""

    id: UUID
    title: str
    description: str | None
    severity: str | None
    source_chunk_ids: list[UUID]


class IntelligenceResponse(BaseModel):
    """Complete structured intelligence snapshot."""

    tasks: list[TaskResponse]
    commitments: list[CommitmentResponse]
    decisions: list[DecisionResponse]
    projects: list[ProjectResponse]
    people: list[PersonResponse]
    risks: list[RiskResponse]