import pytest
import numpy as np

from backend.app.access_engine import AccessCorrelationEngine, evaluate_entry_event


@pytest.mark.asyncio
async def test_cosine_similarity_computation():
    engine = AccessCorrelationEngine()

    # Identical vectors should have similarity 1.0
    v1 = np.ones(512, dtype=np.float32)
    v2 = np.ones(512, dtype=np.float32)
    sim = engine.compute_cosine_similarity(v1, v2)
    assert pytest.approx(sim, 0.001) == 1.0

    # Orthogonal vectors should have similarity 0.0
    v_ortho1 = np.zeros(512, dtype=np.float32)
    v_ortho1[0] = 1.0
    v_ortho2 = np.zeros(512, dtype=np.float32)
    v_ortho2[1] = 1.0
    sim_ortho = engine.compute_cosine_similarity(v_ortho1, v_ortho2)
    assert pytest.approx(sim_ortho, 0.001) == 0.0


@pytest.mark.asyncio
async def test_evaluate_entry_event_tailgating_detection():
    # Tailgating should trigger whenever person count > 1
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = await evaluate_entry_event(
        video_frame=dummy_frame,
        scanned_rfid="EMP-4092",
        simulated_person_count=2,
    )

    assert result["status"] == "TAILGATING"
    assert result["person_count"] == 2
    assert result["match_score_pct"] == 0.0
    assert len(result["bounding_boxes"]) >= 2
    assert "detail" in result


@pytest.mark.asyncio
async def test_evaluate_entry_event_authorized_and_mismatch():
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Normal single person authorization
    res_auth = await evaluate_entry_event(
        video_frame=dummy_frame,
        scanned_rfid="EMP-4092",
        simulated_person_count=1,
    )
    assert res_auth["status"] in ["AUTHORIZED", "MISMATCH"]
    assert res_auth["person_count"] == 1
    assert "bounding_boxes" in res_auth
    assert "match_score_pct" in res_auth
    assert res_auth["match_score_pct"] >= 0.0

    # Test mismatch simulation with revoked/invalid RFID badge
    res_mismatch = await evaluate_entry_event(
        video_frame=dummy_frame,
        scanned_rfid="EMP-REVOKED-999",
        simulated_person_count=1,
    )
    assert res_mismatch["status"] == "MISMATCH"
    assert res_mismatch["match_score_pct"] < 85.0
