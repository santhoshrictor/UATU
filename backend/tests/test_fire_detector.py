"""
Unit and integration tests for Feature 21: Machine Learning Fire & Smoke Detection with:
- Corrected class index mapping: Class 0 = Fire, Class 1 = Smoke (resolving CAM-05 label swap)
- Webcam exclusion: Physical webcams (CAM-01 / device 0/1) disable smoke/fire heuristics
- Dedicated smoke threshold: conf=0.45 (for diffuse semi-transparent smoke)
- Dense-smoke texture & diffusion heuristics
- Standardized critical hazard alert carrying camera ID and zone metadata
"""
import os
from unittest.mock import MagicMock, patch
import numpy as np
import pytest
import cv2

from backend.app.fire_detector import FireDetector, COLOR_FIRE, COLOR_SMOKE
from backend.app.vision_engine import SpatialTracker
from backend.app import live_event_store
from backend.main import create_hazard_alert_payload


def test_fire_detector_initialization():
    """Verify FireDetector initializes with dedicated smoke conf=0.45 and fire conf=0.50."""
    mock_model = MagicMock()
    mock_model.names = {0: "fire", 1: "smoke"}
    detector = FireDetector(model=mock_model)
    assert detector.model == mock_model
    assert detector.smoke_conf_threshold == 0.45
    assert detector.fire_conf_threshold == 0.50


def test_fire_detector_webcam_strict_thresholds():
    """Verify FireDetector configured for webcam applies strict conf=0.85 and disables smoke heuristic."""
    mock_model = MagicMock()
    mock_model.names = {0: "fire", 1: "smoke"}
    detector = FireDetector(model=mock_model, is_webcam=True)
    assert detector.fire_conf_threshold == 0.85
    assert detector.smoke_conf_threshold == 0.85
    assert detector.enable_smoke_heuristic is False


def test_fire_detector_blank_frame_nominal():
    """Verify nominal frame produces no detections and fire_detected is False."""
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    mock_model = MagicMock()
    mock_model.return_value = [MagicMock(boxes=[])]
    mock_model.names = {0: "fire", 1: "smoke"}

    detector = FireDetector(model=mock_model)
    annotated, fire_detected, detections = detector.detect(blank)

    assert fire_detected is False
    assert len(detections) == 0


def test_fire_detector_skips_static_zero_motion_frame():
    """Verify fire detection is skipped entirely on static frames with zero optical flow / motion."""
    frame_static = np.zeros((480, 640, 3), dtype=np.uint8)
    mock_model = MagicMock()

    detector = FireDetector(model=mock_model, enable_motion_gate=True)

    # Frame 1: Initial frame registers prev_gray
    detector.detect(frame_static)
    assert mock_model.call_count == 1

    # Frame 2: Identical frame (motion == 0.0) -> must skip model inference completely!
    _, fire_detected, _ = detector.detect(frame_static)
    assert fire_detected is False
    assert mock_model.call_count == 1, "Model inference should have been skipped on static frame with zero motion"


def test_fire_detector_correct_class_mapping_fire_class_0():
    """
    Verify Class 0 strictly maps to Fire (resolving CAM-05 label confusion):
    Detection of Class 0 with confidence 0.53 is correctly recognized as 'fire',
    NOT mislabeled as smoke.
    """
    mock_box = MagicMock()
    mock_box.conf = [0.53]
    mock_box.cls = [0]  # Class 0: Fire
    mock_box.xyxy = np.array([[120, 100, 320, 300]])

    mock_result = MagicMock()
    mock_result.boxes = [mock_box]

    mock_model = MagicMock()
    mock_model.return_value = [mock_result]
    mock_model.names = {0: "fire", 1: "smoke"}

    detector = FireDetector(
        model=mock_model,
        fire_conf_threshold=0.50,
        temporal_buffer_frames=1,
        enable_motion_gate=False,
    )

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    annotated, fire_detected, detections = detector.detect(frame)

    assert fire_detected is True
    assert len(detections) == 1
    assert detections[0]["class_id"] == 0
    assert detections[0]["class_name"] == "fire"
    assert detector.primary_hazard == "fire"


def test_fire_detector_smoke_lower_threshold_conf_045():
    """
    Verify Class 1 strictly maps to Smoke with dedicated threshold (conf=0.45):
    Smoke at conf=0.48 (Class 1) is accepted since conf >= 0.45.
    """
    mock_box = MagicMock()
    mock_box.conf = [0.48]  # Class 1: Smoke at conf=0.48
    mock_box.cls = [1]
    mock_box.xyxy = np.array([[100, 100, 300, 300]])

    mock_result = MagicMock()
    mock_result.boxes = [mock_box]

    mock_model = MagicMock()
    mock_model.return_value = [mock_result]
    mock_model.names = {0: "fire", 1: "smoke"}

    detector = FireDetector(
        model=mock_model,
        smoke_conf_threshold=0.45,
        temporal_buffer_frames=1,
        enable_motion_gate=False,
    )

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    annotated, fire_detected, detections = detector.detect(frame)

    assert fire_detected is True
    assert len(detections) == 1
    assert detections[0]["class_id"] == 1
    assert detections[0]["class_name"] == "smoke"
    assert detections[0]["confidence"] == 0.48
    assert detector.primary_hazard == "smoke"


def test_fire_detector_fire_rejected_below_threshold():
    """Verify fire detection below fire threshold (e.g. conf=0.40) is rejected."""
    mock_box = MagicMock()
    mock_box.conf = [0.40]  # Below fire threshold 0.50
    mock_box.cls = [0]       # Class 0: Fire
    mock_box.xyxy = np.array([[50, 50, 150, 150]])

    mock_result = MagicMock()
    mock_result.boxes = [mock_box]

    mock_model = MagicMock()
    mock_model.return_value = [mock_result]
    mock_model.names = {0: "fire", 1: "smoke"}

    detector = FireDetector(model=mock_model, fire_conf_threshold=0.50, enable_motion_gate=False)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    annotated, fire_detected, detections = detector.detect(frame)
    assert fire_detected is False
    assert len(detections) == 0


def test_dense_smoke_texture_heuristic():
    """
    Verify dense smoke diffusion heuristic:
    Detects low-frequency gray-scale expansion (dense grey cluster with low edge sharpness)
    even when ML model misses it.
    """
    mock_model = MagicMock()
    mock_model.return_value = [MagicMock(boxes=[])]  # ML model returns 0 boxes
    mock_model.names = {0: "fire", 1: "smoke"}

    detector = FireDetector(
        model=mock_model,
        temporal_buffer_frames=1,
        enable_motion_gate=False,
        enable_smoke_heuristic=True,
    )

    # Frame 1: Background
    f1 = np.full((480, 640, 3), 40, dtype=np.uint8)
    detector.detect(f1)

    # Frame 2: Moving dense grey/white cluster (simulating smoke billowing on CAM-04)
    f2 = f1.copy()
    grey_patch = np.full((120, 120, 3), 160, dtype=np.uint8)
    grey_patch = cv2.GaussianBlur(grey_patch, (25, 25), 0)
    f2[150:270, 200:320] = grey_patch

    annotated, fire_detected, detections = detector.detect(f2)

    assert fire_detected is True
    assert len(detections) >= 1
    assert any(d["class_name"] == "smoke" and d["class_id"] == 1 for d in detections)
    assert detector.primary_hazard == "smoke"


def test_webcam_stream_excludes_fire_smoke_detection():
    """
    Verify Task 1:
    Physical webcam stream (CAM-01 / is_webcam=True) completely disables
    environmental smoke/fire heuristics to prevent false positives in personal workspaces.
    """
    mock_pose_model = MagicMock()
    mock_pose_model.track.return_value = [MagicMock(boxes=[])]

    mock_fire_model = MagicMock()

    tracker = SpatialTracker(
        model=mock_pose_model,
        fire_model=mock_fire_model,
        camera_id="CAM-01",
        zone="Zone 01 // Main Turnstile North",
        is_webcam=True,
    )

    assert tracker.is_webcam is True
    assert tracker.enable_fire_detection is False
    assert tracker.fire_detector is None

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    with patch("backend.app.vision_engine.alert_manager.broadcast_sync") as mock_broadcast:
        _, counts = tracker.process_frame(frame)
        assert counts["fire_detected"] is False
        assert counts["smoke_detected"] is False
        assert mock_broadcast.call_count == 0


def test_critical_hazard_alert_carries_camera_and_zone_context():
    """
    Verify Task 3:
    Detecting fire or smoke triggers standardized WebSocket payload
    with explicit camera ID and zone metadata.
    """
    mock_pose_model = MagicMock()
    mock_pose_model.track.return_value = [MagicMock(boxes=[])]

    mock_box = MagicMock()
    mock_box.conf = [0.85]
    mock_box.cls = [0]  # Class 0: Fire
    mock_box.xyxy = np.array([[100, 100, 250, 250]])

    mock_fire_result = MagicMock()
    mock_fire_result.boxes = [mock_box]

    mock_fire_model = MagicMock()
    mock_fire_model.return_value = [mock_fire_result]
    mock_fire_model.names = {0: "fire", 1: "smoke"}

    tracker = SpatialTracker(
        model=mock_pose_model,
        fire_model=mock_fire_model,
        camera_id="CAM-05",
        zone="Zone 04 // Tier-3 Data Center Vault",
        is_webcam=False,
        alert_cooldown=15.0,
    )
    tracker.fire_detector.enable_motion_gate = False
    tracker.fire_detector.temporal_buffer_frames = 1

    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    with patch("backend.app.vision_engine.alert_manager.broadcast_sync") as mock_broadcast:
        _, counts = tracker.process_frame(frame)
        assert counts["fire_detected"] is True
        assert counts["hazard_type"] == "fire"

        assert mock_broadcast.call_count == 1
        payload = mock_broadcast.call_args[0][0]

        assert payload["id"].startswith("EVT-HAZARD-")
        assert payload["type"] == "CRITICAL HAZARD: FIRE / SMOKE DETECTED"
        assert payload["level"] == "CRITICAL"
        assert payload["camera"] == "CAM-05"
        assert payload["zone"] == "Zone 04 // Tier-3 Data Center Vault"
        assert "CAM-05" in payload["detail"]
        assert "Zone 04 // Tier-3 Data Center Vault" in payload["detail"]
        assert payload["acknowledged"] is False
        assert "IST" in payload["time"]


def test_create_hazard_alert_payload_helper():
    """Verify backend/main.py create_hazard_alert_payload helper output matches schema."""
    payload = create_hazard_alert_payload(
        camera_id="CAM-05",
        zone="Zone 04 // Tier-3 Data Center Vault",
        timestamp=1792772500,
    )
    assert payload == {
        "id": "EVT-HAZARD-1792772500",
        "time": payload["time"],
        "zone": "Zone 04 // Tier-3 Data Center Vault",
        "camera": "CAM-05",
        "type": "CRITICAL HAZARD: FIRE / SMOKE DETECTED",
        "level": "CRITICAL",
        "detail": "Hazard identified on CAM-05 (Zone 04 // Tier-3 Data Center Vault). Immediate evacuation required.",
        "acknowledged": False,
    }
    assert "IST" in payload["time"]


def test_hazard_trigger_fire_endpoint():
    """Verify POST /api/hazard/trigger-fire immediately emits CRITICAL HAZARD: FIRE / FLAME."""
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    res = client.post("/api/hazard/trigger-fire?camera_id=CAM-03&zone=Zone%2003%20//%20Warehouse")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "alert" in data
    alert = data["alert"]
    assert alert["camera"] == "CAM-03"
    assert alert["type"] == "CRITICAL HAZARD: FIRE / FLAME"
    assert alert["level"] == "CRITICAL"
    assert alert["severity"] == "CRITICAL"
    assert alert["snapshot_url"].startswith("http://127.0.0.1:8000/api/snapshots/")

    # Confirm snapshot exists on disk
    fname = alert["snapshot_url"].split("/")[-1]
    snap_path = os.path.join(live_event_store.SNAPSHOTS_DIR, fname)
    assert os.path.exists(snap_path), f"Evidence snapshot missing at {snap_path}"


def test_cam03_fire_flame_detection_flags_critical_fire_flame():
    """Verify that when CAM-03 detects a flame signature, it immediately flags CRITICAL HAZARD: FIRE / FLAME."""
    from backend.app.vision_engine import SpatialTracker
    from backend.app.core.websocket_manager import alert_manager

    mock_model = MagicMock()
    mock_model.track.return_value = [MagicMock(boxes=[])]
    mock_fire_model = MagicMock()
    mock_fire_model.names = {0: "fire", 1: "smoke"}

    tracker = SpatialTracker(
        model=mock_model,
        fire_model=mock_fire_model,
        camera_id="CAM-03",
        zone="Zone 03 // Warehouse",
    )
    tracker.is_stream_active = True
    alert_manager.resume_stream_dispatch("CAM-03")

    # Real fire box passing CAM-03 contour and conf requirements
    real_fire_box = MagicMock()
    real_fire_box.conf = [0.93]
    real_fire_box.cls = [0]
    real_fire_box.xyxy = [np.array([100, 100, 200, 200])]  # 100x100 = 10,000 px > 2000
    mock_fire_model.return_value = [MagicMock(boxes=[real_fire_box])]

    with patch("backend.app.vision_engine.alert_manager.broadcast_sync") as mock_broadcast:
        for i in range(5):
            frame = np.ones((480, 640, 3), dtype=np.uint8) * (100 + i * 10)
            _, counts = tracker.process_frame(frame)

        assert counts["fire_detected"] is True
        assert mock_broadcast.call_count >= 1
        payload = mock_broadcast.call_args[0][0]
        assert payload["type"] == "CRITICAL HAZARD: FIRE / FLAME"
        assert payload["camera"] == "CAM-03"
        assert payload["level"] == "CRITICAL"

