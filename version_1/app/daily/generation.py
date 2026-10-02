"""LLM generation for daily intelligence."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.daily.context import DailyIntelligenceContext
from app.llm.models import LLMResponse, Message
from app.llm.structured import StructuredLLMProvider


DAILY_GENERATION_SYSTEM_PROMPT = """\
You are the daily intelligence generation component of PAIS.

Generate a concise daily intelligence brief using only the structured
context supplied by the application.

Rules:
- Use only facts present in the supplied context.
- Do not invent facts, people, projects, risks, dates, or actions.
- Do not change or recompute priority scores.
- Do not create new priorities.
- Treat the deterministic priority ordering as authoritative.
- Do not infer information that is not explicitly present.
- Summarize rather than speculate.
- Preserve uncertainty when the supplied context contains uncertainty.
- If a section has no information, return an empty list.
- Keep each item concise and useful.
- The summary should describe the day's actionable and informational state.
"""


class DailyBrief(BaseModel):
    """Structured daily intelligence generated from PAIS context."""

    summary: str = Field(min_length=1)
    priorities: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    changes: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class DailyGenerationResult:
    """Result produced by daily intelligence generation."""

    brief: DailyBrief
    model: str | None
    latency_ms: float | None


class DailyGenerationService:
    """Generate a structured daily intelligence brief."""

    def __init__(
        self,
        *,
        structured_llm: StructuredLLMProvider,
    ) -> None:
        self.structured_llm = structured_llm

    async def generate(
        self,
        context: DailyIntelligenceContext,
        *,
        temperature: float = 0.0,
    ) -> DailyGenerationResult:
        """Generate daily intelligence from enriched structured context."""

        if self._is_empty(context):
            return DailyGenerationResult(
                brief=DailyBrief(
                    summary=(
                        "No actionable items or recent intelligence "
                        "were found for this day."
                    ),
                ),
                model=None,
                latency_ms=None,
            )

        messages = self._build_messages(context)

        brief, response = await self.structured_llm.generate(
            messages,
            schema=DailyBrief,
            temperature=temperature,
        )

        return self._build_result(
            brief=brief,
            response=response,
        )

    @staticmethod
    def _is_empty(
        context: DailyIntelligenceContext,
    ) -> bool:
        """Return whether the context contains no daily intelligence."""

        return not (
            context.prioritized_items
            or context.recent_decisions
            or context.recent_changes
            or context.recent_projects
            or context.recent_people
            or context.recent_risks
        )

    @staticmethod
    def _build_messages(
        context: DailyIntelligenceContext,
    ) -> list[Message]:
        """Build the daily intelligence generation prompt."""

        sections: list[str] = []

        sections.append(
            "DAY:\n"
            f"{context.day.isoformat()}\n"
            f"TIMEZONE: {context.timezone_name}"
        )

        sections.append(
            DailyGenerationService._format_priorities(
                context
            )
        )

        sections.append(
            DailyGenerationService._format_decisions(
                context
            )
        )

        sections.append(
            DailyGenerationService._format_changes(
                context
            )
        )

        sections.append(
            DailyGenerationService._format_projects(
                context
            )
        )

        sections.append(
            DailyGenerationService._format_people(
                context
            )
        )

        sections.append(
            DailyGenerationService._format_risks(
                context
            )
        )

        user_prompt = (
            "DAILY CONTEXT:\n\n"
            + "\n\n".join(sections)
            + "\n\nGenerate the daily intelligence brief."
        )

        return [
            Message(
                role="system",
                content=DAILY_GENERATION_SYSTEM_PROMPT,
            ),
            Message(
                role="user",
                content=user_prompt,
            ),
        ]

    @staticmethod
    def _format_priorities(
        context: DailyIntelligenceContext,
    ) -> str:
        if not context.prioritized_items:
            return "PRIORITIZED ITEMS:\nNone"

        lines = ["PRIORITIZED ITEMS:"]

        for index, item in enumerate(
            context.prioritized_items,
            start=1,
        ):
            reasons = "; ".join(
                reason.message
                for reason in item.reasons
            )

            lines.append(
                f"{index}. "
                f"[{item.item_type.value}] "
                f"{item.title} "
                f"(score={item.score}; "
                f"reasons={reasons})"
            )

        return "\n".join(lines)

    @staticmethod
    def _format_decisions(
        context: DailyIntelligenceContext,
    ) -> str:
        if not context.recent_decisions:
            return "RECENT DECISIONS:\nNone"

        lines = ["RECENT DECISIONS:"]

        for decision in context.recent_decisions:
            lines.append(
                f"- {decision.title}: "
                f"{decision.description} "
                f"(status={decision.status})"
            )

        return "\n".join(lines)

    @staticmethod
    def _format_changes(
        context: DailyIntelligenceContext,
    ) -> str:
        if not context.recent_changes:
            return "RECENT CHANGES:\nNone"

        lines = ["RECENT CHANGES:"]

        for change in context.recent_changes:
            lines.append(
                f"- {change.entity_type}: "
                f"{change.entity_id} "
                f"(changed_at={change.changed_at.isoformat()})"
            )

        return "\n".join(lines)

    @staticmethod
    def _format_projects(
        context: DailyIntelligenceContext,
    ) -> str:
        if not context.recent_projects:
            return "RECENT PROJECTS:\nNone"

        lines = ["RECENT PROJECTS:"]

        for project in context.recent_projects:
            description = (
                project.description
                if project.description
                else "No description."
            )

            lines.append(
                f"- {project.name}: "
                f"{description} "
                f"(status={project.status})"
            )

        return "\n".join(lines)

    @staticmethod
    def _format_people(
        context: DailyIntelligenceContext,
    ) -> str:
        if not context.recent_people:
            return "RECENT PEOPLE:\nNone"

        lines = ["RECENT PEOPLE:"]

        for person in context.recent_people:
            email = (
                f", email={person.email}"
                if person.email
                else ""
            )

            lines.append(
                f"- {person.name}{email}"
            )

        return "\n".join(lines)

    @staticmethod
    def _format_risks(
        context: DailyIntelligenceContext,
    ) -> str:
        if not context.recent_risks:
            return "RECENT RISKS:\nNone"

        lines = ["RECENT RISKS:"]

        for risk in context.recent_risks:
            description = (
                risk.description
                if risk.description
                else "No description."
            )

            severity = (
                risk.severity
                if risk.severity
                else "unspecified"
            )

            lines.append(
                f"- {risk.title}: "
                f"{description} "
                f"(severity={severity})"
            )

        return "\n".join(lines)

    @staticmethod
    def _build_result(
        *,
        brief: DailyBrief,
        response: LLMResponse,
    ) -> DailyGenerationResult:
        """Convert structured provider output into a generation result."""

        return DailyGenerationResult(
            brief=brief,
            model=response.model,
            latency_ms=response.latency_ms,
        )