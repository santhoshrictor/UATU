"""Opt-in live timezone checks."""

from knowledge import current_time


def test_live_india_clock_has_timezone_and_date():
    result = current_time("India")
    assert result["timezone"] == "Asia/Kolkata"
    assert result["utc_offset"] == "+0530"
