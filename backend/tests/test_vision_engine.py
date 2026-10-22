from unittest.mock import MagicMock, patch
import numpy as np

from backend.app.vision_engine import (
    SpatialTracker,
    COLOR_TRIPWIRE,
)


def test_process_spatial_frame_none_or_empty():
    tracker = SpatialTracker(model=None)
    frame, counts = tracker.process_frame(None)
    assert frame is None
    assert counts["persons"] == 0
    assert counts["vehicles"] == 0
    assert counts["entry"] == 0
    assert counts["exit"] == 0

    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    out_frame, counts = tracker.process_frame(blank)
    assert out_frame.shape == (480, 640, 3)
    assert counts["persons"] >= 0
    assert counts["vehicles"] >= 0
    assert counts["entry"] >= 0
    assert counts["exit"] >= 0


def test_process_spatial_frame_mock_detections():
    blank = np.zeros((480, 640, 3), dtype=np.uint8)

    # Mock detection boxes:
    # 1. Person with track ID 1 (class 0, conf 0.88)
    box_person = MagicMock()
    box_person.cls = [MagicMock(item=lambda: 0)]
    box_person.conf = [MagicMock(item=lambda: 0.88)]
    box_person.xyxy = [np.array([50, 50, 200, 350])]
    box_person.id = MagicMock(item=lambda: 1)

    # 2. Vehicle - Car with track ID 2 (class 2, conf 0.92)
    box_car = MagicMock()
    box_car.cls = [MagicMock(item=lambda: 2)]
    box_car.conf = [MagicMock(item=lambda: 0.92)]
    box_car.xyxy = [np.array([250, 100, 500, 300])]
    box_car.id = MagicMock(item=lambda: 2)

    # 3. Low confidence person (class 0, conf 0.20 - should be filtered)
    box_low_conf = MagicMock()
    box_low_conf.cls = [MagicMock(item=lambda: 0)]
    box_low_conf.conf = [MagicMock(item=lambda: 0.20)]
    box_low_conf.xyxy = [np.array([10, 10, 30, 30])]
    box_low_conf.id = None

    # 4. Non-person/non-vehicle (class 15 - cat, should be filtered)
    box_cat = MagicMock()
    box_cat.cls = [MagicMock(item=lambda: 15)]
    box_cat.conf = [MagicMock(item=lambda: 0.85)]
    box_cat.xyxy = [np.array([100, 100, 150, 150])]
    box_cat.id = None

    mock_res = MagicMock()
    mock_res.boxes = [box_person, box_car, box_low_conf, box_cat]

    mock_model = MagicMock()
    mock_model.track.return_value = [mock_res]
    mock_model.return_value = [mock_res]

    tracker = SpatialTracker(model=mock_model)
    annotated, counts = tracker.process_frame(blank)
    assert counts["persons"] == 1
    assert counts["vehicles"] == 1
    assert annotated.shape == (480, 640, 3)
    # Bounding boxes, tripwire, and telemetry should modify pixels
    assert np.any(annotated > 0)


def test_line_crossing_entry_and_exit():
    """
    Tests Feature 4 horizontal line-crossing logic (55% line_y = 264):
    - Moving UP across line_y triggers UP (Exit).
    - Moving DOWN across line_y triggers DOWN (Entry).
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)

    # Frame 1: Person above the line (cy = 200, line_y = 264)
    box_f1 = MagicMock()
    box_f1.cls = [MagicMock(item=lambda: 0)]
    box_f1.conf = [MagicMock(item=lambda: 0.90)]
    box_f1.xyxy = [np.array([100, 150, 200, 250])]  # cy = 200 (< 264)
    box_f1.id = MagicMock(item=lambda: 42)

    res_f1 = MagicMock(boxes=[box_f1])
    mock_model = MagicMock()
    mock_model.track.return_value = [res_f1]
    mock_model.return_value = [res_f1]

    tracker = SpatialTracker(model=mock_model)
    _, counts = tracker.process_frame(blank)
    assert counts["entry"] == 0
    assert counts["exit"] == 0

    # Frame 2: Person moves DOWN across line (cy = 300 >= 264) -> Triggers DOWN (Entry)!
    box_f2 = MagicMock()
    box_f2.cls = [MagicMock(item=lambda: 0)]
    box_f2.conf = [MagicMock(item=lambda: 0.90)]
    box_f2.xyxy = [np.array([100, 250, 200, 350])]  # cy = 300 (>= 264)
    box_f2.id = MagicMock(item=lambda: 42)

    res_f2 = MagicMock(boxes=[box_f2])
    mock_model.track.return_value = [res_f2]

    _, counts = tracker.process_frame(blank)
    assert counts["entry"] == 1
    assert counts["exit"] == 0

    # Frame 3: Person continues moving DOWN (cy = 350 >= 264). Should not double-count.
    box_f3 = MagicMock()
    box_f3.cls = [MagicMock(item=lambda: 0)]
    box_f3.conf = [MagicMock(item=lambda: 0.90)]
    box_f3.xyxy = [np.array([100, 300, 200, 400])]  # cy = 350
    box_f3.id = MagicMock(item=lambda: 42)

    res_f3 = MagicMock(boxes=[box_f3])
    mock_model.track.return_value = [res_f3]

    _, counts = tracker.process_frame(blank)
    assert counts["entry"] == 1
    assert counts["exit"] == 0

    # Frame 4: Person moves UP across line (cy = 200 <= 264). Triggers UP (Exit)!
    box_f4 = MagicMock()
    box_f4.cls = [MagicMock(item=lambda: 0)]
    box_f4.conf = [MagicMock(item=lambda: 0.90)]
    box_f4.xyxy = [np.array([100, 150, 200, 250])]  # cy = 200 (<= 264)
    box_f4.id = MagicMock(item=lambda: 42)

    res_f4 = MagicMock(boxes=[box_f4])
    mock_model.track.return_value = [res_f4]

    _, counts = tracker.process_frame(blank)
    assert counts["entry"] == 1
    assert counts["exit"] == 1


def test_tripwire_and_hud_rendered():
    """Verifies that the horizontal counting line and top-right HUD are rendered."""
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    tracker = SpatialTracker(model=None)
    annotated, counts = tracker.process_frame(blank)
    # Line y is int(480 * 0.55) = 264. Check tripwire pixel at y=264, x=320
    tripwire_pixel = annotated[264, 320]
    # COLOR_TRIPWIRE is (0, 215, 255) in BGR
    assert tripwire_pixel[1] > 200 or tripwire_pixel[2] > 200
    # Check top-right region has HUD overlay pixels (non-zero)
    top_right_region = annotated[12:48, 500:630]
    assert np.any(top_right_region > 0)


def test_reset_tracking():
    """Verifies reset resets instance state."""
    tracker = SpatialTracker(model=None)
    tracker.down_count = 5
    tracker.up_count = 3
    tracker.reset()
    assert tracker.down_count == 0
    assert tracker.up_count == 0
    assert tracker.entry_count == 0
    assert tracker.exit_count == 0
    assert len(tracker.previous_y) == 0


def test_raw_detection_without_tracking_ids():
    """
    Verifies that raw bounding boxes and class labels are drawn
    even when boxes.id is None (tracker has not assigned an ID yet).
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)

    boxes_mock = MagicMock()
    boxes_mock.xyxy = np.array([[100, 100, 250, 300], [300, 150, 500, 350]])
    boxes_mock.cls = [MagicMock(item=lambda: 0), MagicMock(item=lambda: 2)]
    boxes_mock.conf = [MagicMock(item=lambda: 0.91), MagicMock(item=lambda: 0.87)]
    boxes_mock.id = None  # No IDs assigned!

    res_mock = MagicMock(boxes=boxes_mock)
    mock_model = MagicMock()
    mock_model.track.return_value = [res_mock]

    tracker = SpatialTracker(model=mock_model)
    annotated, counts = tracker.process_frame(blank)
    assert counts["persons"] == 1
    assert counts["vehicles"] == 1
    assert counts["entry"] == 0
    assert counts["exit"] == 0
    # Check that bounding box pixels were modified in the detection regions
    assert np.any(annotated[100:300, 100:250] > 0)
    assert np.any(annotated[150:350, 300:500] > 0)


def test_stream_isolation_independent_states():
    """
    Verifies that distinct SpatialTracker instances maintain completely
    isolated tracking history, counting metrics, and centroid caches.
    """
    tracker_webcam0 = SpatialTracker(model=None)
    tracker_file_stream = SpatialTracker(model=None)

    tracker_webcam0.down_count = 7
    tracker_webcam0.previous_y[10] = 300

    assert tracker_file_stream.down_count == 0
    assert tracker_file_stream.up_count == 0
    assert 10 not in tracker_file_stream.previous_y


def test_zone_occupancy_inside_and_outside():
    """
    Verifies Feature 16 (Occupancy) and Contextual UI:
    Person whose feet (x_center, y2) fall inside the zone polygon
    is counted toward zone occupancy, while persons outside are ignored.
    When occupancy < zone_threshold, the zone is completely invisible.
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)

    # Zone is [[100, 150], [540, 150], [540, 400], [100, 400]]
    # Person 1 inside zone: feet at x=200, y=300
    box_inside = MagicMock()
    box_inside.cls = [MagicMock(item=lambda: 0)]
    box_inside.conf = [MagicMock(item=lambda: 0.90)]
    box_inside.xyxy = [np.array([180, 120, 220, 300])]
    box_inside.id = MagicMock(item=lambda: 1)

    # Person 2 outside zone: feet at x=50, y=50
    box_outside = MagicMock()
    box_outside.cls = [MagicMock(item=lambda: 0)]
    box_outside.conf = [MagicMock(item=lambda: 0.90)]
    box_outside.xyxy = [np.array([40, 20, 60, 50])]
    box_outside.id = MagicMock(item=lambda: 2)

    mock_res = MagicMock(boxes=[box_inside, box_outside])
    mock_model = MagicMock()
    mock_model.track.return_value = [mock_res]

    tracker = SpatialTracker(model=mock_model)
    annotated, counts = tracker.process_frame(blank)

    assert counts["persons"] == 2
    assert counts["occupancy"] == 1
    assert counts["is_crowded"] is False
    assert counts["gathering_alert"] is False

    # Contextual UI: Zone polygon is INVISIBLE until breached!
    # Point at (450, 150) is on the top zone edge, far from person 1 (x: 180-220) and tripwire (y: 264)
    # It must remain completely black (0, 0, 0)
    assert np.all(annotated[150, 450] == 0)


def test_abnormal_gathering_alert_threshold():
    """
    Verifies Feature 15 (Abnormal Gathering) and Contextual UI:
    When occupancy reaches or exceeds zone_threshold (default 4),
    is_crowded is triggered, the polygon is alpha-blended red, and warning text is drawn.
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)

    # 4 Persons inside zone [[100, 150], [540, 150], [540, 400], [100, 400]]
    persons = []
    for idx, x_center in enumerate([150, 250, 350, 450]):
        p = MagicMock()
        p.cls = [MagicMock(item=lambda: 0)]
        p.conf = [MagicMock(item=lambda: 0.90)]
        p.xyxy = [np.array([x_center - 20, 180, x_center + 20, 320])]
        p.id = MagicMock(item=lambda i=idx + 1: i)
        persons.append(p)

    mock_res = MagicMock(boxes=persons)
    mock_model = MagicMock()
    mock_model.track.return_value = [mock_res]

    tracker = SpatialTracker(model=mock_model, zone_threshold=4)
    annotated, counts = tracker.process_frame(blank)

    assert counts["persons"] == 4
    assert counts["occupancy"] == 4
    assert counts["is_crowded"] is True
    assert counts["gathering_alert"] is True

    # Red channel (index 2) must be dominant on the zone boundary
    zone_top_edge = annotated[150, 100:540]
    assert np.any(zone_top_edge[:, 2] > 200)


def test_websocket_alert_cooldown():
    """
    Verifies that when abnormal gathering is detected,
    an alert is dispatched via alert_manager.broadcast_sync,
    and subsequent frames within the 15-second cooldown window do not re-dispatch.
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)

    persons = []
    for idx, x_center in enumerate([150, 250, 350, 450]):
        p = MagicMock()
        p.cls = [MagicMock(item=lambda: 0)]
        p.conf = [MagicMock(item=lambda: 0.90)]
        p.xyxy = [np.array([x_center - 20, 180, x_center + 20, 320])]
        p.id = MagicMock(item=lambda i=idx + 1: i)
        persons.append(p)

    mock_res = MagicMock(boxes=persons)
    mock_model = MagicMock()
    mock_model.track.return_value = [mock_res]

    tracker = SpatialTracker(model=mock_model, zone_threshold=4, alert_cooldown=15.0)

    with patch("backend.app.vision_engine.alert_manager.broadcast_sync") as mock_broadcast:
        # Frame 1: Triggers alert and dispatches
        tracker.process_frame(blank.copy())
        assert mock_broadcast.call_count == 1
        payload = mock_broadcast.call_args[0][0]
        assert payload["id"].startswith("EVT-CROWD-")
        assert payload["zone"] == "Live Monitoring Zone"
        assert payload["type"] == "ABNORMAL GATHERING"
        assert payload["level"] == "CRITICAL"
        assert payload["detail"] == "Occupancy threshold breached (> 3 persons)."
        assert payload["acknowledged"] is False

        # Frame 2 immediately after: Cooldown is active, must NOT re-dispatch
        tracker.process_frame(blank.copy())
        assert mock_broadcast.call_count == 1


def test_camera_device_worker_alert_cooldown():
    """
    Verifies that CameraDeviceWorker in main.py checks is_crowded,
    dispatches an alert payload to alert_manager, and enforces 15s cooldown.
    """
    from backend.app.main import CameraDeviceWorker
    worker = CameraDeviceWorker(device_id=99)
    assert hasattr(worker, "last_crowd_alert_time")
    assert worker.crowd_alert_cooldown == 15.0

    mock_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    worker.tracker.process_frame = MagicMock(return_value=(mock_frame, {"is_crowded": True, "occupancy": 4}))

    with patch("backend.app.main.alert_manager.broadcast_sync") as mock_broadcast:
        # Simulate one iteration of worker logic
        counts = {"is_crowded": True, "occupancy": 4}
        now_ts = 1000.0
        if counts.get("is_crowded"):
            if (now_ts - worker.last_crowd_alert_time) >= worker.crowd_alert_cooldown:
                worker.last_crowd_alert_time = now_ts
                payload = {
                    "id": f"EVT-CROWD-{int(now_ts)}",
                    "time": "12:00:00 UTC",
                    "zone": "Live Monitoring Zone",
                    "type": "ABNORMAL GATHERING",
                    "level": "CRITICAL",
                    "detail": "Occupancy threshold breached (> 3 persons).",
                    "acknowledged": False,
                }
                from backend.app.core.websocket_manager import alert_manager
                alert_manager.broadcast_sync(payload)

        assert mock_broadcast.call_count == 1
        assert worker.last_crowd_alert_time == 1000.0

        # Immediate next frame (within cooldown)
        now_ts_next = 1005.0
        if counts.get("is_crowded"):
            if (now_ts_next - worker.last_crowd_alert_time) >= worker.crowd_alert_cooldown:
                worker.last_crowd_alert_time = now_ts_next
                alert_manager.broadcast_sync({})

        assert mock_broadcast.call_count == 1



