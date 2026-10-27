"""
Unit & integration tests for PPE (Personal Protective Equipment) Detection pipeline:
- YOLOv8 PPE model loading and class mappings
- Compliant vs non-compliant equipment classification (Hardhat, Safety Vest, Mask)
- Compliance rate and violation list calculation
- /api/ppe/status and /api/ppe/trigger-violation endpoints
"""
import os
from unittest.mock import MagicMock, patch
import numpy as np
import pytest
import cv2

from backend.app.ppe_detector import PPEDetector, CLASS_MAP
from backend.app import live_event_store


def test_ppe_detector_initialization():
    """Verify PPEDetector initializes with certified YOLO model weights."""
    detector = PPEDetector()
    assert detector.model is not None, "PPE model should be loaded"
    assert detector.conf_threshold == 0.30


def test_ppe_class_mapping_logic():
    """Verify standard class mapping for PPE compliant and violation categories."""
    detector = PPEDetector(model=MagicMock())

    # Compliant
    c1, is_comp1, label1 = detector._map_class(0, "Hardhat")
    assert c1 == "hardhat" and is_comp1 is True and "Hardhat" in label1

    c2, is_comp2, label2 = detector._map_class(7, "Safety Vest")
    assert c2 == "safety_vest" and is_comp2 is True and "Vest" in label2

    c3, is_comp3, label3 = detector._map_class(1, "Mask")
    assert c3 == "mask" and is_comp3 is True and "Mask" in label3

    # Violations
    c4, is_comp4, label4 = detector._map_class(2, "NO-Hardhat")
    assert c4 == "no_hardhat" and is_comp4 is False and "Missing" in label4

    c5, is_comp5, label5 = detector._map_class(4, "NO-Safety Vest")
    assert c5 == "no_vest" and is_comp5 is False and "Missing" in label5


def test_ppe_detector_blank_frame_nominal():
    """Verify that blank frame yields 100% compliance and 0 violations."""
    detector = PPEDetector()
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    frame, summary, items = detector.detect(blank)

    assert summary["total_detected"] == 0
    assert summary["violation_count"] == 0
    assert summary["compliance_rate"] == 100.0
    assert summary["has_violation"] is False
    assert len(summary["violations"]) == 0


def test_ppe_detector_with_mock_violations():
    """Verify detection summaries when missing hard hat and safety vest are detected."""
    mock_model = MagicMock()
    mock_model.names = {0: "Hardhat", 2: "NO-Hardhat", 4: "NO-Safety Vest", 7: "Safety Vest"}

    # Mock box 1: NO-Hardhat
    box_no_hat = MagicMock()
    box_no_hat.conf = [0.91]
    box_no_hat.cls = [2]
    box_no_hat.xyxy = [np.array([150, 50, 250, 150])]

    # Mock box 2: Safety Vest (Compliant)
    box_vest = MagicMock()
    box_vest.conf = [0.88]
    box_vest.cls = [7]
    box_vest.xyxy = [np.array([140, 150, 260, 350])]

    mock_result = MagicMock()
    mock_result.boxes = [box_no_hat, box_vest]
    mock_model.return_value = [mock_result]

    detector = PPEDetector(model=mock_model, temporal_buffer_frames=1)
    test_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    _, summary, items = detector.detect(test_frame)

    assert summary["total_detected"] == 2
    assert summary["compliant_count"] == 1
    assert summary["violation_count"] == 1
    assert summary["compliance_rate"] == 50.0
    assert summary["has_violation"] is True
    assert "Missing Hardhat" in summary["violations"]


def test_ppe_status_api_endpoint():
    """Verify GET /api/ppe/status returns compliance metrics."""
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    res = client.get("/api/ppe/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "compliance_rate" in data
    assert "monitored_cameras" in data
    assert "required_equipment" in data
    assert "Hardhat" in data["required_equipment"]


def test_ppe_trigger_violation_endpoint():
    """Verify POST /api/ppe/trigger-violation creates snapshot and broadcasts PPE violation."""
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    res = client.post(
        "/api/ppe/trigger-violation?camera_id=CAM-04&zone=Zone%2002%20//%20Precision%20Machining%20Line"
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "alert" in data
    alert = data["alert"]

    assert alert["camera"] == "CAM-04"
    assert alert["type"] == "PPE COMPLIANCE VIOLATION"
    assert alert["level"] == "WARNING"
    assert alert["snapshot_url"].startswith("http://127.0.0.1:8000/api/snapshots/")

    # Confirm snapshot exists on disk
    fname = alert["snapshot_url"].split("/")[-1]
    snap_path = os.path.join(live_event_store.SNAPSHOTS_DIR, fname)
    assert os.path.exists(snap_path), f"Evidence snapshot missing at {snap_path}"
