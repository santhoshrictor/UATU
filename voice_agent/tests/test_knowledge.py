from datetime import datetime, timezone

import pytest

from knowledge import KnowledgeTools, current_time


def test_india_clock_is_converted_from_actual_instant_not_model_memory():
    now = datetime(2026, 10, 20, 20, 45, tzinfo=timezone.utc)
    result = current_time("India", now=now)
    assert result["timezone"] == "Asia/Kolkata"
    assert result["time_24h"] == "02:15:00"
    assert result["date"] == "2026-10-21"
    assert current_time("IST", now=now)["time_24h"] == "02:15:00"


def test_unknown_timezone_is_not_guessed():
    with pytest.raises(ValueError):
        current_time("Madeup/Nowhere")


@pytest.mark.asyncio
async def test_knowledge_tools_get_current_time():
    tools = KnowledgeTools()
    assert len(tools.tools) == 1
    result = await tools.get_current_time(None, "Asia/Kolkata")
    assert result["timezone"] == "Asia/Kolkata"
    assert "time_24h" in result
    assert "date" in result
