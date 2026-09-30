"""Models for structured intelligence extraction."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class IntelligenceSource(BaseModel):
    """Source location supporting an extracted intelligence item."""

    chunk_id: UUID


class TaskCandidate(BaseModel):
    """Potential task extracted from source information."""

    description: str = Field(min_length=1)
    owner: str | None = None
    due_at: datetime | None = None
    priority: str | None = None
    sources: list[IntelligenceSource] = Field(min_length=1)


class CommitmentCandidate(BaseModel):
    """Potential commitment extracted from source information."""

    description: str = Field(min_length=1)
    owner: str | None = None
    deadline_at: datetime | None = None
    sources: list[IntelligenceSource] = Field(min_length=1)


class DecisionCandidate(BaseModel):
    """Potential decision extracted from source information."""

    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    decision_date: datetime | None = None
    sources: list[IntelligenceSource] = Field(min_length=1)


class ProjectCandidate(BaseModel):
    """Potential project extracted from source information."""

    name: str = Field(min_length=1)
    description: str | None = None
    sources: list[IntelligenceSource] = Field(min_length=1)


class PersonCandidate(BaseModel):
    """Potential person extracted from source information."""

    name: str = Field(min_length=1)
    email: str | None = None
    sources: list[IntelligenceSource] = Field(min_length=1)


class RiskCandidate(BaseModel):
    """Potential risk extracted from source information."""

    title: str = Field(min_length=1)
    description: str | None = None
    severity: str | None = None
    sources: list[IntelligenceSource] = Field(min_length=1)


class FollowUpCandidate(BaseModel):
    """Potential follow-up item extracted from source information."""

    description: str = Field(min_length=1)
    owner: str | None = None
    due_at: datetime | None = None
    sources: list[IntelligenceSource] = Field(min_length=1)


class DeadlineCandidate(BaseModel):
    """Potential deadline extracted from source information."""

    description: str = Field(min_length=1)
    due_at: datetime
    sources: list[IntelligenceSource] = Field(min_length=1)


class StructuredIntelligence(BaseModel):
    """Validated structured intelligence extracted from source material."""

    tasks: list[TaskCandidate] = Field(default_factory=list)
    commitments: list[CommitmentCandidate] = Field(default_factory=list)
    decisions: list[DecisionCandidate] = Field(default_factory=list)
    projects: list[ProjectCandidate] = Field(default_factory=list)
    people: list[PersonCandidate] = Field(default_factory=list)
    risks: list[RiskCandidate] = Field(default_factory=list)
    follow_ups: list[FollowUpCandidate] = Field(default_factory=list)
    deadlines: list[DeadlineCandidate] = Field(default_factory=list)