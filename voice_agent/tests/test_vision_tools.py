import io
from unittest.mock import MagicMock

import pytest
from PIL import Image

from uatu_seed_data import HUMAN_REVIEW_DISCLAIMER
from vision_tools import VisionTools


def test_vision_tools_registration():
    tools = VisionTools()
    assert len(tools.tools) == 2
    tool_names = {t.__name__ for t in tools.tools}
    assert tool_names == {"inspect_physical_camera", "inspect_uatu_camera_feed"}


@pytest.mark.asyncio
async def test_inspect_physical_camera_mocked(monkeypatch):
    tools = VisionTools()
    dummy_img = Image.new("RGB", (100, 100), color="green")

    monkeypatch.setattr("vision_tools._capture_webcam_frame", lambda: dummy_img)
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "Microcontroller circuit on desk."
    mock_client.models.generate_content.return_value = mock_resp
    monkeypatch.setattr(tools, "_get_genai_client", lambda: mock_client)

    res = await tools.inspect_physical_camera(None, question="What is on my desk?")
    assert res["status"] == "success"
    assert "Microcontroller" in res["analysis"]
    assert "webcam_" in res["snapshot_saved_to"]
    assert res["human_review_notice"] == HUMAN_REVIEW_DISCLAIMER


@pytest.mark.asyncio
async def test_inspect_uatu_camera_feed_fallback_and_disclaimer(monkeypatch):
    tools = VisionTools()
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "Workshop 2 CNC machines running; worker wearing high-vis vest."
    mock_client.models.generate_content.return_value = mock_resp
    monkeypatch.setattr(tools, "_get_genai_client", lambda: mock_client)

    res = await tools.inspect_uatu_camera_feed(
        None,
        camera_id="CAM-04",
        question="Check PPE compliance and lathe operation.",
    )

    assert res["status"] == "success"
    assert res["camera_id"] == "CAM-04"
    assert "high-vis vest" in res["analysis"]
    assert "CAM-04_" in res["snapshot_saved_to"]
    assert res["human_review_notice"] == HUMAN_REVIEW_DISCLAIMER


@pytest.mark.asyncio
async def test_inspect_uatu_camera_feed_live_stream_grab(monkeypatch):
    tools = VisionTools()

    # Generate a realistic JPEG byte payload
    img = Image.new("RGB", (320, 240), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    jpeg_bytes = buf.getvalue()

    def mock_stream_get(*args, **kwargs):
        class MockResp:
            status = 200

            async def read(self):
                return jpeg_bytes

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                pass

        return MockResp()

    monkeypatch.setattr("aiohttp.ClientSession.get", mock_stream_get)

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "Turnstile entry area clear; personnel queue within markers."
    mock_client.models.generate_content.return_value = mock_resp
    monkeypatch.setattr(tools, "_get_genai_client", lambda: mock_client)

    res = await tools.inspect_uatu_camera_feed(
        None,
        camera_id="CAM-01",
        question="Inspect turnstile queue density.",
    )

    assert res["status"] == "success"
    assert res["camera_id"] == "CAM-01"
    assert "FASTAPI_STREAM" in res["source"]
    assert "Turnstile" in res["analysis"]
    assert res["human_review_notice"] == HUMAN_REVIEW_DISCLAIMER
