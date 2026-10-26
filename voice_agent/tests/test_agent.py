import os
import textwrap
from unittest.mock import Mock

import pytest
from google.genai import types


def test_agent_tools_and_voice_configuration(monkeypatch):
    from agent import Assistant, google

    constructor = Mock(return_value=Mock())
    monkeypatch.setattr(google.realtime, "RealtimeModel", constructor)

    assistant = Assistant()
    tool_names = {t.id for t in assistant.tools}
    expected = {
        "get_current_time",
        "get_hardware_status",
        "get_security_and_network_audit",
        "get_camera_and_stream_health",
        "calculate_and_audit_video_storage",
        "inspect_physical_camera",
        "inspect_uatu_camera_feed",
        "search_video_events",
        "get_zone_occupancy_and_traffic",
        "query_access_control_and_enrolled_users",
        "acknowledge_or_escalate_alert",
        "generate_daily_incident_summary",
        "get_recent_audit_trail",
        "end_call",
    }
    assert expected.issubset(tool_names)

    config = constructor.call_args.kwargs["realtime_input_config"]
    activity = config.automatic_activity_detection
    assert activity.disabled is False
    assert (
        activity.start_of_speech_sensitivity
        == types.StartSensitivity.START_SENSITIVITY_HIGH
    )
    assert activity.silence_duration_ms == 250


# Live evaluations (opt-in)
@pytest.mark.skipif(
    os.getenv("IRIS_RUN_LIVE_EVALS") != "1",
    reason="Live model evaluations are opt-in: set IRIS_RUN_LIVE_EVALS=1 with provider credentials.",
)
@pytest.mark.asyncio
async def test_offers_assistance() -> None:
    from livekit.agents import AgentSession, inference, llm

    from agent import Assistant

    def _judge_llm() -> llm.LLM:
        return inference.LLM(model="openai/gpt-4.1-mini")

    async with (
        _judge_llm() as judge_llm,
        AgentSession() as session,
    ):
        await session.start(Assistant())
        result = await session.run(user_input="Hello")
        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                judge_llm,
                intent=textwrap.dedent(
                    """\
                    Greets the user in a friendly manner.
                    """
                ),
            )
        )
        result.expect.no_more_events()
