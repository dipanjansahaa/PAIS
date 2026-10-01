"""Unit tests for daily intelligence service."""

from datetime import date, datetime, timezone

import pytest

from app.daily.service import DailyIntelligenceService


def test_utc_day_window_for_india():
    """Asia/Kolkata local midnight should convert to the correct UTC window."""

    start, end = DailyIntelligenceService._utc_day_window(
        day=date(2026, 10, 2),
        timezone_name="Asia/Kolkata",
    )

    assert start == datetime(
        2026,
        10,
        1,
        18,
        30,
    )

    assert end == datetime(
        2026,
        10,
        2,
        18,
        30,
    )


def test_utc_day_window_for_utc():
    """UTC should preserve the calendar-day boundaries."""

    start, end = DailyIntelligenceService._utc_day_window(
        day=date(2026, 10, 2),
        timezone_name="UTC",
    )

    assert start == datetime(
        2026,
        10,
        2,
        0,
        0,
    )

    assert end == datetime(
        2026,
        10,
        3,
        0,
        0,
    )


def test_utc_day_window_rejects_unknown_timezone():
    """Invalid timezone names should fail explicitly."""

    with pytest.raises(
        ValueError,
        match="Unknown timezone",
    ):
        DailyIntelligenceService._utc_day_window(
            day=date(2026, 10, 2),
            timezone_name="Not/A/Timezone",
        )