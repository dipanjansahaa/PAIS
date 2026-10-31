"""Conservative deterministic entity linking for existing PAIS entities."""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.database.models.person import Person

LinkStatus = Literal["matched", "not_found", "ambiguous"]


@dataclass(frozen=True, slots=True)
class PersonLinkResult:
    """Outcome of resolving an owner reference against a user's people."""

    status: LinkStatus
    person_id: UUID | None = None
    matched_by: Literal["name", "email"] | None = None
    candidate_ids: tuple[UUID, ...] = ()


class EntityLinkingService:
    """Resolve person references by exact normalized name or email only.

    This deliberately avoids fuzzy matching and substring matches: an uncertain
    reference is left unlinked rather than creating a potentially false edge.
    The caller must pass only people belonging to the requesting user.
    """

    def resolve_person_reference(
        self,
        reference: str | None,
        *,
        people: Sequence[Person],
    ) -> PersonLinkResult:
        """Resolve a reference to exactly one person or report ambiguity.

        References containing ``@`` are treated as email references and are
        matched only against email fields. Other references are exact name
        matches after Unicode normalization, case-folding, and whitespace
        normalization.
        """
        normalized = _normalize(reference)
        if not normalized:
            return PersonLinkResult(status="not_found")

        if "@" in normalized:
            matches = [person for person in people if _normalize_email(person.email) == normalized]
            matched_by: Literal["name", "email"] = "email"
        else:
            matches = [person for person in people if _normalize(person.name) == normalized]
            matched_by = "name"

        # Defensively deduplicate repeated references to the same entity ID.
        unique: dict[UUID, Person] = {person.id: person for person in matches}
        candidate_ids = tuple(unique)
        if not candidate_ids:
            return PersonLinkResult(status="not_found")
        if len(candidate_ids) > 1:
            return PersonLinkResult(
                status="ambiguous",
                candidate_ids=candidate_ids,
            )
        return PersonLinkResult(
            status="matched",
            person_id=candidate_ids[0],
            matched_by=matched_by,
            candidate_ids=candidate_ids,
        )


def _normalize(value: str | None) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKC", value)
    return " ".join(normalized.split()).casefold()


def _normalize_email(value: str | None) -> str:
    return _normalize(value)
