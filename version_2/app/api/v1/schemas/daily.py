"""Schemas for the daily intelligence API."""

from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator


class DailyRequest(BaseModel):
    """Request parameters for daily intelligence."""

    day: date
    timezone_name: str = Field(min_length=1)

    @field_validator("timezone_name")
    @classmethod
    def validate_timezone_name(cls, value: str) -> str:
        """Normalize and validate the IANA timezone name."""

        value = value.strip()

        if not value:
            raise ValueError("Timezone name must not be empty.")

        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(
                f"Unknown timezone: {value}"
            ) from exc

        return value


class DailyResponse(BaseModel):
    """Daily intelligence API response."""

    day: date
    timezone_name: str

    summary: str
    priorities: list[str]
    decisions: list[str]
    changes: list[str]
    risks: list[str]

    model: str | None
    latency_ms: float | None