"""End-to-end workflow for daily intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.daily.context import DailyContextBuilder, DailyIntelligenceContext
from app.daily.enrichment import DailyEntityContextEnricher
from app.daily.generation import DailyGenerationResult, DailyGenerationService
from app.daily.models import DailySnapshot
from app.daily.priority import PriorityEngine
from app.daily.service import DailyIntelligenceService


@dataclass(frozen=True, slots=True)
class DailyWorkflowResult:
    """Complete result produced by the daily intelligence workflow."""

    snapshot: DailySnapshot
    context: DailyIntelligenceContext
    generation: DailyGenerationResult


class DailyWorkflowService:
    """Orchestrate deterministic daily intelligence and LLM generation."""

    def __init__(
        self,
        *,
        snapshot_service: DailyIntelligenceService | None = None,
        priority_engine: PriorityEngine | None = None,
        context_builder: DailyContextBuilder | None = None,
        entity_enricher: DailyEntityContextEnricher | None = None,
        generation_service: DailyGenerationService,
    ) -> None:
        self.snapshot_service = (
            snapshot_service
            if snapshot_service is not None
            else DailyIntelligenceService()
        )
        self.priority_engine = (
            priority_engine
            if priority_engine is not None
            else PriorityEngine()
        )
        self.context_builder = (
            context_builder
            if context_builder is not None
            else DailyContextBuilder()
        )
        self.entity_enricher = (
            entity_enricher
            if entity_enricher is not None
            else DailyEntityContextEnricher()
        )
        self.generation_service = generation_service

    async def run(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        day: date,
        timezone_name: str,
        temperature: float = 0.0,
    ) -> DailyWorkflowResult:
        """Run the complete daily intelligence workflow."""

        snapshot = await self.snapshot_service.build_snapshot(
            session,
            user_id=user_id,
            day=day,
            timezone_name=timezone_name,
        )

        prioritized_items = self.priority_engine.prioritize_snapshot(
            snapshot
        )

        context = self.context_builder.build(
            snapshot,
            prioritized_items,
        )

        context = await self.entity_enricher.enrich(
            session,
            user_id=user_id,
            context=context,
        )

        generation = await self.generation_service.generate(
            context,
            temperature=temperature,
        )

        return DailyWorkflowResult(
            snapshot=snapshot,
            context=context,
            generation=generation,
        )