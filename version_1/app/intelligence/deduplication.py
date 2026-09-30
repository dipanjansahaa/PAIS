"""Deterministic deduplication for structured intelligence."""

from __future__ import annotations

import unicodedata
from collections.abc import Callable, Iterable
from typing import TypeVar

from app.intelligence.models import (
    CommitmentCandidate,
    DecisionCandidate,
    IntelligenceSource,
    StructuredIntelligence,
    TaskCandidate,
)


Candidate = TypeVar(
    "Candidate",
    TaskCandidate,
    CommitmentCandidate,
    DecisionCandidate,
)


def normalize_text(value: str) -> str:
    """Normalize text for deterministic identity comparison."""

    value = unicodedata.normalize("NFKC", value)

    value = " ".join(value.split())

    return value.casefold()


def _normalize_optional_text(value: str | None) -> str | None:
    """Normalize an optional identity field."""

    if value is None:
        return None

    return normalize_text(value)


def _merge_sources(
    first: list[IntelligenceSource],
    second: list[IntelligenceSource],
) -> list[IntelligenceSource]:
    """Merge sources while preserving first-seen order."""

    result: list[IntelligenceSource] = []
    seen = set()

    for source in [*first, *second]:
        if source.chunk_id in seen:
            continue

        seen.add(source.chunk_id)
        result.append(source)

    return result


def _compatible(
    first,
    second,
    fields: tuple[str, ...],
) -> bool:
    """Return whether all mergeable fields are compatible.

    A field is compatible when both candidates either:
    - have the same value, or
    - one candidate has no value.
    """

    for field in fields:
        first_value = getattr(first, field)
        second_value = getattr(second, field)

        if (
            first_value is not None
            and second_value is not None
            and first_value != second_value
        ):
            return False

    return True


def _merge_optional_fields(
    first,
    second,
    fields: tuple[str, ...],
):
    """Fill missing fields from the second candidate."""

    updates = {}

    for field in fields:
        first_value = getattr(first, field)
        second_value = getattr(second, field)

        if first_value is None and second_value is not None:
            updates[field] = second_value

    if updates:
        first = first.model_copy(update=updates)

    return first


def deduplicate_tasks(
    tasks: Iterable[TaskCandidate],
) -> list[TaskCandidate]:
    """Deduplicate task candidates deterministically."""

    result: list[TaskCandidate] = []
    indexes: dict[tuple[str, str | None], int] = {}

    mergeable_fields = ("due_at", "priority")

    for task in tasks:
        key = (
            normalize_text(task.description),
            _normalize_optional_text(task.owner),
        )

        existing_index = indexes.get(key)

        if existing_index is None:
            indexes[key] = len(result)
            result.append(task)
            continue

        existing = result[existing_index]

        if not _compatible(
            existing,
            task,
            mergeable_fields,
        ):
            result.append(task)
            continue

        merged = _merge_optional_fields(
            existing,
            task,
            mergeable_fields,
        )

        merged = merged.model_copy(
            update={
                "sources": _merge_sources(
                    existing.sources,
                    task.sources,
                )
            }
        )

        result[existing_index] = merged

    return result


def deduplicate_commitments(
    commitments: Iterable[CommitmentCandidate],
) -> list[CommitmentCandidate]:
    """Deduplicate commitment candidates deterministically."""

    result: list[CommitmentCandidate] = []
    indexes: dict[tuple[str, str | None], int] = {}

    mergeable_fields = ("deadline_at",)

    for commitment in commitments:
        key = (
            normalize_text(commitment.description),
            _normalize_optional_text(commitment.owner),
        )

        existing_index = indexes.get(key)

        if existing_index is None:
            indexes[key] = len(result)
            result.append(commitment)
            continue

        existing = result[existing_index]

        if not _compatible(
            existing,
            commitment,
            mergeable_fields,
        ):
            result.append(commitment)
            continue

        merged = _merge_optional_fields(
            existing,
            commitment,
            mergeable_fields,
        )

        merged = merged.model_copy(
            update={
                "sources": _merge_sources(
                    existing.sources,
                    commitment.sources,
                )
            }
        )

        result[existing_index] = merged

    return result


def deduplicate_decisions(
    decisions: Iterable[DecisionCandidate],
) -> list[DecisionCandidate]:
    """Deduplicate decision candidates deterministically."""

    result: list[DecisionCandidate] = []
    indexes: dict[tuple[str, str], int] = {}

    mergeable_fields = ("decision_date",)

    for decision in decisions:
        key = (
            normalize_text(decision.title),
            normalize_text(decision.description),
        )

        existing_index = indexes.get(key)

        if existing_index is None:
            indexes[key] = len(result)
            result.append(decision)
            continue

        existing = result[existing_index]

        if not _compatible(
            existing,
            decision,
            mergeable_fields,
        ):
            result.append(decision)
            continue

        merged = _merge_optional_fields(
            existing,
            decision,
            mergeable_fields,
        )

        merged = merged.model_copy(
            update={
                "sources": _merge_sources(
                    existing.sources,
                    decision.sources,
                )
            }
        )

        result[existing_index] = merged

    return result


def deduplicate_intelligence(
    intelligence: StructuredIntelligence,
) -> StructuredIntelligence:
    """Deduplicate supported structured intelligence categories."""

    return intelligence.model_copy(
        update={
            "tasks": deduplicate_tasks(
                intelligence.tasks,
            ),
            "commitments": deduplicate_commitments(
                intelligence.commitments,
            ),
            "decisions": deduplicate_decisions(
                intelligence.decisions,
            ),
        }
    )