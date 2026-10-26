from unittest.mock import Mock

import pytest
from google.genai import types


@pytest.mark.asyncio
async def test_noise_resistant_turn_detection_preserves_real_interruptions(monkeypatch):
    from agent import Assistant, google

    constructor = Mock(return_value=Mock())
    monkeypatch.setattr(google.realtime, "RealtimeModel", constructor)
    Assistant()
    config = constructor.call_args.kwargs["realtime_input_config"]
    activity = config.automatic_activity_detection
    assert activity.disabled is False
    assert (
        activity.start_of_speech_sensitivity
        == types.StartSensitivity.START_SENSITIVITY_HIGH
    )
    assert (
        activity.end_of_speech_sensitivity == types.EndSensitivity.END_SENSITIVITY_HIGH
    )
    assert activity.silence_duration_ms == 250
    assert activity.prefix_padding_ms == 100
    assert (
        config.activity_handling == types.ActivityHandling.START_OF_ACTIVITY_INTERRUPTS
    )
