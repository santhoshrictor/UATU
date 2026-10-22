from unittest.mock import MagicMock, patch
import cv2
import numpy as np

from backend.app.vision_engine import process_spatial_frame


def test_process_spatial_frame_none_or_empty():
    frame, counts = process_spatial_frame(None)
    assert frame is None
    assert counts == {"persons": 0, "vehicles": 0}

    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    out_frame, counts = process_spatial_frame(blank)
    assert out_frame.shape == (480, 640, 3)
    assert counts["persons"] >= 0
    assert counts["vehicles"] >= 0


def test_process_spatial_frame_mock_detections():
    blank = np.zeros((480, 640, 3), dtype=np.uint8)

    # Mock detection boxes:
    # 1. Person (class 0, conf 0.88)
    box_person = MagicMock()
    box_person.cls = [MagicMock(item=lambda: 0)]
    box_person.conf = [MagicMock(item=lambda: 0.88)]
    box_person.xyxy = [np.array([50, 50, 200, 350])]

    # 2. Vehicle - Car (class 2, conf 0.92)
    box_car = MagicMock()
    box_car.cls = [MagicMock(item=lambda: 2)]
    box_car.conf = [MagicMock(item=lambda: 0.92)]
    box_car.xyxy = [np.array([250, 100, 500, 300])]

    # 3. Low confidence person (class 0, conf 0.20 - should be filtered)
    box_low_conf = MagicMock()
    box_low_conf.cls = [MagicMock(item=lambda: 0)]
    box_low_conf.conf = [MagicMock(item=lambda: 0.20)]
    box_low_conf.xyxy = [np.array([10, 10, 30, 30])]

    # 4. Non-person/non-vehicle (class 15 - cat, should be filtered)
    box_cat = MagicMock()
    box_cat.cls = [MagicMock(item=lambda: 15)]
    box_cat.conf = [MagicMock(item=lambda: 0.85)]
    box_cat.xyxy = [np.array([100, 100, 150, 150])]

    mock_res = MagicMock()
    mock_res.boxes = [box_person, box_car, box_low_conf, box_cat]

    mock_model = MagicMock(return_value=[mock_res])

    with patch("backend.app.vision_engine.yolo_spatial_model", mock_model):
        annotated, counts = process_spatial_frame(blank)
        assert counts["persons"] == 1
        assert counts["vehicles"] == 1
        assert annotated.shape == (480, 640, 3)
        # Should have drawn bounding boxes so pixels are modified
        assert np.any(annotated > 0)
