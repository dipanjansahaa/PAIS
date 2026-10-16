"""Authentication domain models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuthenticatedIdentity:
    """Verified identity extracted from an authentication token."""

    subject: str